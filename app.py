import streamlit as st
import os
import tempfile
import psutil
import time

# استيراد الدوال من ملف trans.py
from trans import transcribe_video_to_text, translate_text_marian, generate_srt_file, format_timestamp

st.set_page_config(layout="wide", page_title="أداة ترجمة الفيديو بالذكاء الاصطناعي")

# --- دالة لمراقبة موارد النظام ---
def get_system_info():
    cpu_percent = psutil.cpu_percent(interval=None)
    ram_percent = psutil.virtual_memory().percent
    ram_used_gb = psutil.virtual_memory().used / (1024**3)
    ram_total_gb = psutil.virtual_memory().total / (1024**3)
    return cpu_percent, ram_percent, ram_used_gb, ram_total_gb

# --- عنوان التطبيق ---
st.title("أداة ترجمة الفيديو بالذكاء الاصطناعي 🎥")
st.markdown("---")

# --- وصف الأداة والملاحظات حول الجودة والأداء ---
st.info("""
هذه الأداة تقوم بتحويل الكلام في الفيديو إلى نص، تكتشف اللغة تلقائياً، تترجم النص، وتنشئ ملف ترجمة SRT جاهز للاستخدام.
**ملاحظات هامة:**
* **جودة الترجمة:** تعتمد دقة الترجمة على نموذج الذكاء الاصطناعي المستخدم (MarianMT). قد لا تكون مثالية في التعامل مع التعبيرات الاصطلاحية أو العامية. يُنصح بمراجعة ملف الترجمة يدوياً بعد التنزيل.
* **الأداء واستهلاك الموارد:** معالجة الفيديو والترجمة تستهلك موارد عالية (خاصة RAM ووحدة المعالجة المركزية CPU). الفيديوهات الطويلة جداً ستستغرق وقتاً طويلاً.
""")
st.markdown("---")

# --- تحميل الفيديو ---
st.header("1. تحميل ملف الفيديو")
uploaded_file = st.file_uploader("اختر ملف فيديو (mp4, mov, avi, etc.)", type=["mp4", "mov", "avi", "mkv"])

# --- خيارات الترجمة والموارد ---
st.header("2. تحديد خيارات الترجمة واستهلاك الموارد")

language_options = {
    "العربية": "ar", "الإنجليزية": "en", "الفرنسية": "fr", "الإسبانية": "es", "العبرية": "he"
}
target_lang_display = st.selectbox(
    "اختر اللغة التي تريد الترجمة إليها:",
    options=list(language_options.keys()),
    index=0
)
target_translation_lang = language_options[target_lang_display]

whisper_model_options = {
    "tiny": "Tiny (أقل دقة، أسرع، أقل استهلاك للرام)",
    "base": "Base (دقة متوازنة، سرعة متوسطة، استهلاك رام متوسط)",
    "small": "Small (دقة جيدة، أبطأ قليلاً، استهلاك رام أعلى)",
    "medium": "Medium (دقة عالية جداً، أبطأ، استهلاك رام عالي)",
    "large": "Large (أعلى دقة، الأبطأ على CPU، أعلى استهلاك للرام)"
}
selected_whisper_model = st.selectbox(
    "اختر حجم نموذج Whisper:",
    options=list(whisper_model_options.keys()),
    format_func=lambda x: whisper_model_options[x],
    index=1
)
st.info("نصيحة: نماذج 'medium' و 'large' قد تتطلب جهازاً ذا موارد عالية (خاصة RAM).")


# --- زر بدء العملية ---
st.header("3. بدء عملية الترجمة")
if st.button("بدء الترجمة وإنشاء ملف SRT"):
    if uploaded_file is not None:
        # استخدام st.status لإظهار التقدم والرسائل
        with st.status("جاري معالجة الفيديو...", expanded=True) as status_indicator:
            cpu_p, ram_p, ram_u_gb, ram_t_gb = get_system_info()
            status_indicator.write(f"📈 **تهيئة النظام ومراقبة الموارد...**")
            status_indicator.write(f"الموارد الحالية: CPU: {cpu_p:.1f}%, RAM: {ram_p:.1f}% ({ram_u_gb:.2f}/{ram_t_gb:.2f} GB)")

            video_path = None
            try:
                # حفظ الملف المؤقت
                status_indicator.write("📁 جاري حفظ ملف الفيديو مؤقتاً...")
                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uploaded_file.name.split('.')[-1]}") as tmp_video_file:
                    tmp_video_file.write(uploaded_file.read())
                    video_path = tmp_video_file.name
                status_indicator.write(f"✓ تم حفظ الفيديو مؤقتاً في: {video_path}")

                # 1. تحويل الفيديو إلى نص واكتشاف اللغة
                status_indicator.write("🎤 **جاري استخراج الصوت وتحويله إلى نص...**")
                status_indicator.write(f"   - استخدام نموذج Whisper بحجم: {selected_whisper_model.upper()}")
                transcription_result, detected_lang = transcribe_video_to_text(video_path, model_size=selected_whisper_model) # لا ترجع total_vid_duration هنا بعد

                if transcription_result:
                    status_indicator.write("✓ تم تحويل الفيديو إلى نص بنجاح!")
                    cpu_p, ram_p, ram_u_gb, ram_t_gb = get_system_info()
                    status_indicator.write(f"الموارد بعد التحويل: CPU: {cpu_p:.1f}%, RAM: {ram_p:.1f}% ({ram_u_gb:.2f}/{ram_t_gb:.2f} GB)")
                    st.subheader("النص الأصلي المكتشف:")
                    st.text(transcription_result['text'])
                    st.write(f"**اللغة المكتشفة:** {detected_lang.upper()}")

                    # 2. الترجمة
                    supported_translation_pairs_keys = [
                        "en-ar", "ar-en", "en-fr", "fr-en", "en-es", "es-en", "he-ar", "ar-he"
                    ]

                    if detected_lang == 'unknown' or f"{detected_lang}-{target_translation_lang}" not in supported_translation_pairs_keys:
                        st.warning(f"⚠️ **تحذير: لم يتمكن Whisper من اكتشاف لغة الفيديو أو لا يوجد نموذج ترجمة لـ {detected_lang.upper()} إلى {target_translation_lang.upper()}. لن تتم الترجمة.**")
                        translated_segments = []
                    else:
                        status_indicator.write(f"🌐 **جاري الترجمة من {detected_lang.upper()} إلى {target_translation_lang.upper()}...**")
                        translated_segments = []
                        translation_progress_bar = st.progress(0, text="تقدم الترجمة: 0%")

                        for i, segment in enumerate(transcription_result['segments']):
                            original_text = segment['text'].strip()
                            if original_text:
                                translated_text = translate_text_marian(original_text, source_lang=detected_lang, target_lang=target_translation_lang)
                                if translated_text:
                                    translated_segments.append({
                                        'start': segment['start'],
                                        'end': segment['end'],
                                        'original_text': original_text,
                                        'translated_text': translated_text
                                    })
                                else:
                                    translated_segments.append({
                                        'start': segment['start'],
                                        'end': segment['end'],
                                        'original_text': original_text,
                                        'translated_text': original_text + " (فشل في الترجمة)"
                                    })
                                progress_val = (i + 1) / len(transcription_result['segments'])
                                translation_progress_bar.progress(progress_val, text=f"تقدم الترجمة: {progress_val:.1%}")
                            else:
                                translated_segments.append({
                                    'start': segment['start'],
                                    'end': segment['end'],
                                    'original_text': "",
                                    'translated_text': ""
                                })
                            if (i + 1) % 10 == 0 or (i + 1) == len(transcription_result['segments']):
                                cpu_p, ram_p, ram_u_gb, ram_t_gb = get_system_info()
                                status_indicator.write(f"الموارد أثناء الترجمة: CPU: {cpu_p:.1f}%, RAM: {ram_p:.1f}% ({ram_u_gb:.2f}/{ram_t_gb:.2f} GB)")

                        status_indicator.write("✓ تمت الترجمة بنجاح!")
                        cpu_p, ram_p, ram_u_gb, ram_t_gb = get_system_info()
                        status_indicator.write(f"الموارد بعد الترجمة: CPU: {cpu_p:.1f}%, RAM: {ram_p:.1f}% ({ram_u_gb:.2f}/{ram_t_gb:.2f} GB)")

                        st.subheader("المقاطع المترجمة:")
                        for segment in translated_segments:
                            st.write(f"**[{format_timestamp(segment['start'])} --> {format_timestamp(segment['end'])}]**")
                            st.write(f"**الأصلي:** {segment['original_text']}")
                            st.write(f"**المترجم:** {segment['translated_text']}")
                            st.write("---")

                        # 3. توليد ملف SRT
                        if translated_segments:
                            status_indicator.write("📄 **جاري إنشاء ملف SRT...**")
                            base_name = os.path.splitext(uploaded_file.name)[0]
                            srt_output_filename = os.path.join(tempfile.gettempdir(), f"{base_name}_translated.srt")

                            generate_srt_file(translated_segments, output_filename=srt_output_filename)

                            st.success("تم إنشاء ملف SRT بنجاح!")
                            status_indicator.write("✓ تم إنشاء ملف SRT.")

                            with open(srt_output_filename, "r", encoding="utf-8") as f:
                                st.download_button(
                                    label="تحميل ملف الترجمة (SRT)",
                                    data=f.read(),
                                    file_name=f"{base_name}_translated.srt",
                                    mime="text/plain"
                                )
                            os.remove(srt_output_filename) # حذف ملف SRT المؤقت بعد التنزيل
                        else:
                            st.warning("⚠️ لا توجد مقاطع مترجمة لإنشاء ملف SRT.")

                    status_indicator.update(label="تم الانتهاء من المعالجة!", state="complete", expanded=False)
                else:
                    st.error("❌ فشلت عملية تحويل الفيديو إلى نص. الرجاء مراجعة سجل الأخطاء.")
                    status_indicator.update(label="فشل في المعالجة!", state="error", expanded=True)

            except Exception as e:
                st.error(f"❌ حدث خطأ غير متوقع أثناء المعالجة: {e}")
                st.exception(e)
                status_indicator.update(label="فشل في المعالجة!", state="error", expanded=True)
            finally:
                if video_path and os.path.exists(video_path):
                    os.remove(video_path)
                    status_indicator.write("🗑️ تم حذف ملف الفيديو المؤقت.")

    else:
            st.warning("⚠️ الرجاء تحميل ملف فيديو أولاً لبدء الترجمة.")

st.markdown("---")
st.caption("Ibrahim Owenah.")


