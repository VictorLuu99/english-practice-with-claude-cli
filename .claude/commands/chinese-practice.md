---
description: Luyện nói tiếng Trung (Mandarin) — Claude đưa câu Việt qua TTS, bạn nói Mandarin, Claude feedback Hanzi + Pinyin + tone
---

Bắt đầu **Mandarin Chinese Speaking Practice** session ngay bây giờ.

Đọc file `.claude/skills/chinese-practice.md` để biết toàn bộ luật chơi (vòng lặp, chủ đề, feedback format có Hanzi + Pinyin + tone correction, edge cases), rồi vận hành loop theo đúng skill đó.

**Tóm tắt nhanh:**
1. In welcome banner:
   ```
   🎯 Mandarin Practice — 普通话 feedback + move on, stateless.
      Gõ "stop" hoặc "停" để dừng. 加油!
   ```
2. Sinh 1 câu tiếng Việt random topic (6-14 từ, conversational, trình độ HSK 2-4).
3. In câu Việt kèm prefix `🇻🇳`.
4. Gọi `bash scripts/speak.sh "<câu Việt>"` qua Bash tool (Linh đọc tiếng Việt).
5. Gọi `WHISPER_LANG=zh WHISPER_MODEL=$HOME/.cache/whisper-cpp/ggml-small.bin bash scripts/record.sh` → transcript Hanzi.
6. Feedback theo format trong skill (`🎙️ You said` / `✅ Model` + Pinyin + nghĩa / `📝 Feedback` / `🔊 Tone check` conditional).
7. Đọc Model bằng Tingting (`SPEAK_VOICE=Tingting SPEAK_RATE=140 bash scripts/speak.sh "<Model Mandarin>"`).
8. Đọc feedback Việt bằng Linh + Tingting (`SPEAK_EN_VOICE=Tingting SPEAK_RATE=150 bash scripts/speak.sh "..."`). Bọc mọi Mandarin (Hanzi hoặc Pinyin) trong backticks — `speak.sh` route các chunk backticks sang Tingting, phần Vi sang Linh.
9. Sang câu mới (KHÔNG retry, KHÔNG hỏi).
10. Lặp đến khi user gõ "stop" / "dừng" / "thôi" / "quit" / "停" hoặc Ctrl-C.

Vào câu đầu tiên NGAY, không hỏi topic, không hỏi level.
