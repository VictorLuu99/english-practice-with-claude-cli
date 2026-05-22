---
description: Luyện nói tiếng Anh — Claude đưa câu Việt qua TTS, bạn nói English, Claude feedback
---

Bắt đầu **English Speaking Practice** session ngay bây giờ.

Đọc file `.claude/skills/english-practice.md` để biết toàn bộ luật chơi (vòng lặp, chủ đề, feedback format, edge cases, quy tắc pronunciation note), rồi vận hành loop theo đúng skill đó.

**Tóm tắt nhanh:**
1. In welcome banner:
   ```
   🎯 English Practice — feedback + move on, stateless.
      Gõ "stop" để dừng. Bắt đầu nhé!
   ```
2. Sinh 1 câu tiếng Việt random topic (8-18 từ, conversational, có challenge).
3. In câu Việt kèm prefix `🇻🇳`.
4. Gọi `bash scripts/speak.sh "<câu Việt>"` qua Bash tool.
5. Gọi `bash scripts/record.sh` qua Bash tool → transcript trên stdout.
6. Feedback theo format trong skill (`🎙️ You said` / `✅ Model` / `📝 Feedback` / `🔊 Pronunciation` conditional).
7. Sang câu mới (KHÔNG retry, KHÔNG hỏi).
8. Lặp đến khi user gõ "stop" / "dừng" / "thôi" / "quit" hoặc Ctrl-C.

Vào câu đầu tiên NGAY, không hỏi topic, không hỏi level.
