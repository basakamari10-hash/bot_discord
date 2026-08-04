# 🕌 Islamic.AI Discord Bot

Islamic.AI adalah bot Discord multi-bahasa yang didukung oleh LLM (Groq API) untuk menjawab pertanyaan seputar Islam. Bot ini menggunakan pendekatan **RAG (Retrieval-Augmented Generation)** dengan rujukan langsung dari database Al-Qur'an lokal, Tafsir, dan HadithAPI.

## ✨ Fitur Utama
* **📖 Al-Qur'an & Tafsir:** Pencarian ayat akurat dan sistem *fallback* tafsir otomatis (Ibn Kathir, Al-Jalalayn, Ma'ariful Qur'an).
* **📚 Hadits Terverifikasi:** Integrasi langsung dengan `hadithapi.com` mencakup Kutubus Sittah.
* **⚖️ Fiqh Komparatif:** Bisa menjawab masalah fiqih berdasarkan berbagai mazhab (Syafi'i, Hanafi, dll).
* **🌐 Multi-Language:** Otomatis menerjemahkan jawaban ke bahasa pengguna (Inggris, Indonesia, Jepang, dll) tanpa merubah teks matan Arab.
* **🛡️ Anti-Hallucination:** Guardrail ketat untuk memastikan AI tidak mengarang dalil.

## ⚙️ Persyaratan (Requirements)
* Python 3.9+
* Modul di `requirements.txt`

## 🚀 Cara Menjalankan (Deployment)

1. **Clone repositori ini:**
   ```bash
   git clone [https://github.com/basakamari10-hash/bot_discord.git](https://github.com/basakamari10-hash/bot_discord.git)
   cd bot_discord
