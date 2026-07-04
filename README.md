# 🐘 Zemu — AI-Powered Learning Assistant

Zemu is an interactive, AI-supported quiz-solving platform specially designed for middle school students. The platform adopts a pedagogical approach that guides students to the correct answer by providing progressive hints rather than directly giving away the solution.

🔗 **Live Demo:** [zemu.vercel.app](https://zemu.vercel.app)

---

## 🚀 Quick Start (Local Run)

To run the application locally on your computer and start solving quizzes:

1. Open a terminal (Command Prompt or PowerShell) inside the Zemu project folder.
2. Start the local server with the following Python command:
   ```bash
   python -m http.server 8000
   ```
3. Open your browser and navigate to:
   **[http://localhost:8000](http://localhost:8000)**

---

## 🗺️ Page Flow and Navigation

To deliver a modular and clean user experience, the application is divided into 4 main views:

1. **Subject Selection (`index.html`):** The student chooses the subject they want to study (e.g., Mathematics).
2. **Grade Selection (`sinif.html`):** Under the selected subject, they choose their grade level (Grade 5, 6, 7, or 8).
3. **Quiz Selection (`testler.html`):** Dynamically fetches and lists available quizzes for the chosen grade.
4. **Quiz Solving Screen (`coz.html`):** The main test-solving page featuring interactive question cards, answer verification, scoring, and the draggable Zemu mascot helper.

---

## 🛠️ System Architecture and Technology Stack

### 💻 Frontend (Client-side)
* **HTML5 & CSS3:** Responsive, modern *glassmorphic* design system built entirely with Vanilla CSS.
* **JavaScript (ES6):** Handles client-side navigation using URL query parameters. Includes keyboard shortcuts (`Enter`, `1-4`, Arrow keys) and desktop/mobile drag event listeners for the Zemu mascot.

### 🧠 Backend & AI Pipeline (Python)
* **Mistral AI API:** Generates progressive, pedagogical explanations (AI hints) on demand without revealing the correct choice.
* **ChromaDB & Ollama (RAG):** The local Retrieval-Augmented Generation (RAG) module (`rag_hafıza.py`) vectorizes study notes using the `nomic-embed-text` embedding model and stores them locally in a persistent vector database (`VektorDB`).
* **PyMuPDF (`fitz`):** The `process_new_tests.py` pipeline automatically parses test PDFs, detects questions, crops question region images (`q1.png`, etc.), and populates the database.

---

## 📁 File Structure & Directory Layout

* **`index.html`:** The home screen for subject selection.
* **`sinif.html`:** The grade level selection screen.
* **`testler.html`:** Dynamically lists tests from the JSON database for the selected grade.
* **`coz.html`:** The core quiz interface, handling test state, Zemu widget interactions, and AI hints.
* **`llm.py`:** Configures pedagogical rules and interface with the Mistral API.
* **`rag_hafıza.py`:** Core module managing vector embeddings and local ChromaDB persistence.
* **`process_new_tests.py`:** Automates parsing and image cropping of newly uploaded test documents.
* **`ipucu_ekle.py`:** Script that inserts static hints and generates dynamic AI hints using Mistral API.
* **`data/`:** Directory holding all processed quiz data, images, cropped questions, and `tests_with_hints.json`.
