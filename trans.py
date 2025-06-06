import subprocess
import whisper
import os
import tempfile
from transformers import MarianMTModel, MarianTokenizer
# تم إزالة gTTS و pydub لأنهما لم يعدا يستخدمان في هذا الإصدار المستقر
# ولكن، قد تحتاج لـ pydub إذا كنت تستخدم دالة AudioSegment.silent() في trans.py
# لذا سنبقيها لضمان التوافق مع FFprobe

# دالة لتحويل الثواني إلى تنسيق توقيت SRT (HH:MM:SS,mmm)
def format_timestamp(seconds):
    """
    يحول التوقيت بالثواني إلى تنسيق SRT.
    مثال: 7.123 -> 00:00:07,123
    """
    milliseconds = int((seconds - int(seconds)) * 1000)
    seconds = int(seconds)
    minutes = seconds // 60
    seconds %= 60
    hours = minutes // 60
    minutes %= 60
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"

def generate_srt_file(translated_segments, output_filename="output_subtitles.srt"):
    """
    ينشئ ملف SRT من المقاطع المترجمة.
    """
    print(f"\nجاري إنشاء ملف SRT باسم: {output_filename}")
    try:
        with open(output_filename, "w", encoding="utf-8") as f:
            for i, segment in enumerate(translated_segments):
                start_time = format_timestamp(segment['start'])
                end_time = format_timestamp(segment['end'])
                translated_text = segment['translated_text']

                f.write(f"{i + 1}\n")
                f.write(f"{start_time} --> {end_time}\n")
                f.write(f"{translated_text}\n")
                f.write("\n")
        print(f"تم إنشاء ملف SRT بنجاح في: {os.path.abspath(output_filename)}")
    except Exception as e:
        print(f"خطأ في إنشاء ملف SRT: {e}")

# هذه الدالة ترجع نتائج التحويل واللغة المكتشفة فقط
def transcribe_video_to_text(video_path, output_audio_path="temp_audio.mp3", model_size="base"):
    """
    يستخرج الصوت من الفيديو ويحوله إلى نص باستخدام Whisper، ويكتشف اللغة.
    """
    if not os.path.exists(video_path):
        print(f"خطأ: ملف الفيديو غير موجود في المسار: {video_path}")
        return None, None # في حالة عدم وجود الملف، أعد None لجميع المخرجات

    print(f"1. جاري استخراج الصوت من الفيديو: {video_path}...")
    try:
        # إضافة -hide_banner و -loglevel error لتقليل مخرجات FFmpeg في الطرفية
        command = [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-i", video_path,
            "-vn",
            "-acodec", "libmp3lame",
            "-ab", "192k",
            "-ar", "44100",
            "-y",
            output_audio_path
        ]
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"تم استخراج الصوت إلى: {output_audio_path}")
    except subprocess.CalledProcessError as e:
        print(f"خطأ في استخراج الصوت باستخدام FFmpeg: {e.stderr.decode()}")
        print("الرجاء التأكد من تثبيت FFmpeg بشكل صحيح وإضافته إلى متغيرات PATH في نظامك.")
        return None, None
    except FileNotFoundError:
        print("خطأ: أمر FFmpeg غير موجود. الرجاء التأكد من تثبيت FFmpeg وإضافته إلى متغيرات PATH في نظامك.")
        return None, None

    print(f"2. جاري تحميل نموذج Whisper بحجم '{model_size}' وتحويل الصوت إلى نص...")
    try:
        model = whisper.load_model(model_size)
        result = model.transcribe(output_audio_path, verbose=False) # verbose=False لتقليل المخرجات في الطرفية
        print("اكتملت عملية تحويل الصوت إلى نص بنجاح.")
        detected_language = result.get('language', 'unknown')
        print(f"اللغة المكتشفة في الفيديو: {detected_language.upper()}")

        # في هذا الإصدار، لا نرجع مدة الفيديو الكلية من هنا.
        # سيتم الحصول عليها من FFprobe في app.py.
        return result, detected_language
    except Exception as e:
        print(f"خطأ في تحويل الصوت إلى نص باستخدام Whisper: {e}")
        print("الرجاء التأكد من وجود اتصال بالإنترنت لتنزيل النموذج إذا كانت هذه هي المرة الأولى.")
        return None, None
    finally:
        if os.path.exists(output_audio_path):
            os.remove(output_audio_path)
            print(f"تم حذف الملف الصوتي المؤقت: {output_audio_path}")

def translate_text_marian(text_to_translate, source_lang, target_lang):
    """
    يترجم نصاً باستخدام نموذج MarianMT من Hugging Face.
    """
    model_name = f"Helsinki-NLP/opus-mt-{source_lang}-{target_lang}"

    supported_model_pairs = {
        "en-ar": "Helsinki-NLP/opus-mt-en-ar",
        "ar-en": "Helsinki-NLP/opus-mt-ar-en",
        "en-fr": "Helsinki-NLP/opus-mt-en-fr",
        "fr-en": "Helsinki-NLP/opus-mt-fr-en",
        "en-es": "Helsinki-NLP/opus-mt-en-es",
        "es-en": "Helsinki-NLP/opus-mt-es-en",
        "he-ar": "Helsinki-NLP/opus-mt-he-ar",
        "ar-he": "Helsinki-NLP/opus-mt-ar-he",
        "en-de": "Helsinki-NLP/opus-mt-en-de", # الإنجليزية إلى الألمانية
        "de-en": "Helsinki-NLP/opus-mt-de-en", # الألمانية إلى الإنجليزية
        # أضف المزيد حسب حاجتك
    }

    if f"{source_lang}-{target_lang}" not in supported_model_pairs:
        print(f"خطأ: لا يوجد نموذج ترجمة مباشر متوفر لـ {source_lang.upper()} إلى {target_lang.upper()} في MarianMT حالياً.")
        print("الرجاء التحقق من Hugging Face أو تغيير اللغات.")
        return None

    print(f"جاري تحميل نموذج الترجمة: {model_name}...")
    try:
        tokenizer = MarianTokenizer.from_pretrained(model_name)
        model = MarianMTModel.from_pretrained(model_name)
        print("تم تحميل نموذج الترجمة بنجاح.")

        inputs = tokenizer(text_to_translate, return_tensors="pt", padding=True)
        translated_ids = model.generate(**inputs)
        translated_text = tokenizer.decode(translated_ids[0], skip_special_tokens=True)
        return translated_text
    except Exception as e:
        print(f"خطأ في عملية الترجمة: {e}")
        print(f"تأكد من وجود اتصال بالإنترنت لتحميل نموذج الترجمة {model_name}.")
        return None

# تم حذف الدوال generate_dubbed_audio_track و merge_audio_with_video من هذا الإصدار.
# إذا كنت تريد استعادتها لاحقاً، يمكن إعادتها إلى هنا.

# --- كيفية الاستخدام (الجزء الرئيسي الذي يتم تشغيله عند تنفيذ السكربت) ---
if __name__ == '__main__':
    print("هذا الملف هو مكتبة دوال. الرجاء تشغيل app.py لتشغيل التطبيق بواجهة المستخدم.")
    # my_video_file = "C:/Users/abrahim owinah/Desktop/test.mp4"
    # chosen_model_size = "base"
    # target_translation_lang = "ar"
    #
    # transcription_result_data, detected_lang, total_vid_duration = transcribe_video_to_text(my_video_file, model_size=chosen_model_size)
    #
    # if transcription_result_data:
    #     # ... (بقية منطق التشغيل المباشر لـ trans.py) ...
    #     pass