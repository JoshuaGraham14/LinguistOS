# 📘 Hybrid System Specification  
## Morpho-Syntactic Sentence Generation + Vocabulary Learning App

---

# 1. 🎯 Objective

Build a **hybrid system** that combines:

- A **research-grade sentence generation pipeline**
- A **lightweight language learning app layer**

The system should:
- Generate sentences with controlled morpho-syntactic constraints
- Evaluate and rank sentence quality automatically
- Allow users to:
  - Store vocabulary
  - Practice using generated sentences

---

# 2. 🧠 Design Philosophy

> One system, two modes:
- **Research Mode** → evaluation, experimentation, analysis  
- **Learning Mode** → user-facing vocabulary practice  

### Key Principles:
- Pipeline is the **core**
- App layer is **thin and minimal**
- Avoid overengineering (auth, dashboards, etc.)

---

# 3. 🏗️ System Architecture

Frontend (React / Next.js + Tailwind)
        ↓
Backend API (FastAPI)
        ↓
Core Pipeline Engine
        ↓
NLP Tools (spaCy, Stanza, LanguageTool)
        ↓
Database (PostgreSQL)

---

# 4. 🧩 Core Components

## 4.1 Pipeline Engine (CORE)

### Responsibilities:
- Generate candidate sentences
- Analyze linguistic features
- Validate constraints
- Score and rank outputs

---

## 4.2 Backend (FastAPI)

### Key Endpoints
- POST /api/generate  
- POST /api/practice  
- GET /api/vocab  
- POST /api/vocab  

---

## 4.3 Frontend (Learning Mode)

- Built with React or Next.js + Tailwind
- Pages:
  - Dashboard (vocab list)
  - Practice page
  - Settings

---

## 4.4 Research Mode

- Built with Streamlit
- Features:
  - Constraint controls
  - Candidate sentence table
  - Scoring + validation display
  - Experimentation tools

---

# 5. 🗄️ Database Schema (PostgreSQL)

## Users
- id
- created_at

## Vocab
- id
- user_id
- word
- language

## Practice Logs
- id
- user_id
- word
- sentence
- score

---

# 6. ⚙️ Scoring System

score =
  +1 lemma match
  +1 tense match
  +1 person match
  +1 number match
  - grammar_errors

---

# 7. 🔄 Data Flow

User → Add vocab → Select word → Generate → Score → Display

---

# 8. 🧪 Research Mode

- Manual constraints
- View all candidates
- View scores and validation

---

# 9. 🎓 Evaluation Hooks

Log all inputs and outputs for experiments.

---

# 10. ⚠️ Limitations

- NLP tools imperfect
- Ambiguity in morphology
- Grammar tools not fully reliable

---

# 11. 🚀 Future Work

- ML scoring
- RL training
- Adaptive learning

---

# 12. 🧰 Technology Stack (Final)

## Learning Mode
- React or Next.js
- TypeScript
- Tailwind CSS

## Research Mode
- Streamlit

## Backend
- FastAPI (Python)

## NLP Stack
- spaCy
- Stanza
- LanguageTool

## Database
- PostgreSQL

---

# 13. ✅ Deliverables

- Full-stack app
- Shared backend pipeline
- Research dashboard
- Evaluation capability

---

# 🧠 Final Insight

A **research pipeline at the core**, wrapped in a **real usable app**,  
with separate interfaces optimized for:
- users (React)
- experimentation (Streamlit)
