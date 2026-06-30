# content_grader.py — SERP V6
# Both versions identical here. Stopwords + score cap already merged.
import textstat, re
from collections import Counter

STOPWORDS = {
    "the","a","an","is","to","of","and","in","for","on","with","it","this","that",
    "are","was","be","as","at","by","we","or","from","but","not","have","has","had",
    "do","does","did","will","would","could","should","may","might","can","its","our",
    "your","their","his","her","my","me","him","them","us","so","if","been","more",
    "also","which","when","all","than","into","about","up","out","no","one","just",
    "there","they","you","he","she","i","am","were"
}

def get_ngrams(text: str, n: int) -> list:
    words = [w for w in re.findall(r'\b\w+\b', text.lower()) if w not in STOPWORDS]
    return [" ".join(words[i:i+n]) for i in range(len(words)-n+1)]

def grade_content(text: str, keywords: list = None) -> dict:
    if not text or len(text.strip()) < 100:
        return {"error": "Please paste at least 100 characters for a meaningful analysis."}

    word_count      = len(text.split())
    sentence_count  = textstat.sentence_count(text)
    avg_sent_len    = round(word_count / sentence_count, 2) if sentence_count > 0 else 0

    readability_scores = {
        "flesch_kincaid_grade":          textstat.flesch_kincaid_grade(text),
        "gunning_fog":                   textstat.gunning_fog(text),
        "smog_index":                    textstat.smog_index(text),
        "automated_readability_index":   textstat.automated_readability_index(text),
        "coleman_liau_index":            textstat.coleman_liau_index(text),
    }

    score, suggestions = 0, []
    reading_ease = textstat.flesch_reading_ease(text)
    if reading_ease >= 60:   score += 40; suggestions.append("✅ Readability is excellent.")
    elif reading_ease >= 40: score += 25; suggestions.append("⚠️ Readability could be improved. Use shorter sentences.")
    else:                    score += 10; suggestions.append("❌ Readability is poor. Simplify your language.")

    if word_count > 1200: score += 20; suggestions.append(f"✅ Great word count ({word_count}).")
    else:                 score += 5;  suggestions.append(f"⚠️ Low word count ({word_count}). Add more depth.")

    if keywords:
        found = sum(1 for kw in keywords if re.search(r'\b'+re.escape(kw.lower())+r'\b', text.lower()))
        score += int(40 * found / len(keywords))
        suggestions.append(f"✅ Keyword Inclusion: {found}/{len(keywords)} terms found.")
    else:
        suggestions.append("💡 No keywords provided for analysis.")

    score = min(score, 100)

    ngrams = {k: [f"{w} ({c})" for w, c in Counter(get_ngrams(text, n)).most_common(15)]
              for k, n in [("1-Word",1),("2-Words",2),("3-Words",3),("4-Words",4),("5-Words",5)]}

    verdict = "Well Optimized" if score >= 80 else "Good" if score >= 50 else "Needs Improvement"

    return {
        "content_score": score, "readability_scores": readability_scores,
        "word_count": word_count, "sentence_count": sentence_count,
        "avg_sentence_length": avg_sent_len, "verdict": verdict,
        "suggestions": suggestions, "ngrams": ngrams,
    }
