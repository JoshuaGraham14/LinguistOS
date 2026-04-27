# 📘 Thesis Description  
## Morpho-Syntactic Controlled Sentence Generation for Language Learning

---

# 1. 🎯 Overview

This thesis explores the development of a system for **generating language learning sentences with controlled grammatical structure**, aimed at improving vocabulary acquisition through contextual practice.

Rather than presenting vocabulary as isolated words, the system focuses on generating **meaningful example sentences** that enforce specific grammatical constraints such as tense, person, number, and part of speech.

---

# 2. 🧠 Motivation

Traditional language learning approaches often rely on:
- Flashcards
- Word memorisation
- Static example sentences

These methods can be limited because they:
- Lack contextual variation  
- Do not adapt to learner needs  
- Do not explicitly control grammatical exposure  

At the same time, modern language models can generate fluent text, but they:
- Struggle with **precise grammatical control**
- Can produce inconsistent or incorrect forms
- Do not guarantee pedagogical suitability

This thesis aims to address this gap.

---

# 3. 🔍 Problem Statement

The core problem investigated is:

> How can we reliably generate sentences that include a target vocabulary item while satisfying explicit morpho-syntactic constraints?

This involves two key challenges:

1. **Generation**  
   Producing natural-sounding sentences containing a specific word.

2. **Control and Verification**  
   Ensuring that generated sentences:
   - Use the correct grammatical form  
   - Satisfy specified constraints  
   - Are suitable for learning contexts  

---

# 4. 💡 Proposed Approach

The project adopts a **pipeline-based approach**, combining:

- Sentence generation (e.g. language models)
- Linguistic analysis (e.g. parsing tools)
- Constraint validation
- Scoring and filtering mechanisms

Rather than assuming generation is perfect, the system:
> Treats outputs as candidates and evaluates them against desired constraints.

This enables more reliable control over grammatical features.

---

# 5. 🌍 Multilingual Focus

The system is designed to work across multiple languages, with particular focus on:

- A morphologically rich language (e.g. Hebrew)
- A more widely supported language (e.g. Spanish)

This allows investigation of:
- Tool reliability across languages  
- Differences in grammatical complexity  
- Generalisability of the approach  

---

# 6. 📱 Dual-System Perspective

The project is implemented as a **hybrid system** consisting of:

### 🔬 Research-Oriented Component
- Used to experiment with generation strategies  
- Evaluates constraint satisfaction  
- Enables analysis of system performance  

### 📚 User-Facing Language Learning Component
- Allows users to build vocabulary lists  
- Provides sentence-based practice  
- Applies the underlying system in a realistic learning setting  

These two perspectives ensure the work is both:
- **Scientifically grounded**
- **Practically applicable**

---

# 7. 🧪 Evaluation Goals

The thesis evaluates:

- How accurately constraints are satisfied  
- The reliability of automatic linguistic tools  
- The quality of generated sentences  
- Differences across languages and configurations  

Where possible, both:
- Automatic evaluation  
- Human judgement  

are considered.

---

# 8. ⚠️ Key Challenges

Several challenges are central to this work:

- Imperfect NLP tools (analysis errors)
- Ambiguity in language
- Inconsistent model outputs
- Balancing fluency vs correctness
- Ensuring pedagogical usefulness

These are treated as part of the research problem rather than ignored.

---

# 9. 🚀 Expected Contributions

This thesis aims to contribute:

- A structured pipeline for controlled sentence generation  
- An evaluation of constraint enforcement techniques  
- Insights into tool reliability for morpho-syntactic analysis  
- A demonstration of practical application in language learning  

---

# 10. 🧠 Final Insight

This work sits at the intersection of:

- Natural Language Processing  
- Language Education  
- Human-AI Interaction  

It explores not just whether sentences can be generated, but:

> Whether they can be generated **correctly, controllably, and usefully** for real learners.

---
