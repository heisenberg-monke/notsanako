"""
Curated reading passages for upper-primary Indian students (Grades 3-5).
Aligned with NCERT and NIPUN Bharat foundational reading benchmarks.
Includes both English and Hindi stories with Indian cultural contexts.
"""

from typing import List, Dict, Any, Optional

PASSAGES: List[Dict[str, Any]] = [
    {
        "id": "en-potter-gr3",
        "title": "The Brave Little Potter",
        "grade_level": 3,
        "language": "en",
        "target_wcpm": 65,
        "description": "A cheerful village story about quick thinking and friendship.",
        "text": "Raghu was a cheerful potter in a small village near Mysore. Every morning, he shaped cool clay into round pots and lamps. One rainy afternoon, a tired little monkey took shelter in his workshop. Raghu smiled and offered the monkey a ripe yellow banana. From that day on, the monkey helped Raghu carry dry leaves to the kiln.",
        "difficulty": "Easy",
        "key_vocabulary": ["cheerful", "workshop", "shelter", "potter", "kiln"]
    },
    {
        "id": "en-kalam-gr4",
        "title": "Wings of Curiosity",
        "grade_level": 4,
        "language": "en",
        "target_wcpm": 80,
        "description": "An inspiring tale based on Dr. APJ Abdul Kalam's childhood in Rameswaram.",
        "text": "Young Abdul loved watching sea birds glide gently across the blue ocean. Early every dawn, he walked along the sandy shore to deliver newspapers to the townspeople. His science teacher once took the class to the seashore to show how birds flap their wings to stay balanced in strong wind. That simple lesson sparked a lifelong dream in Abdul to build rockets that soar into space.",
        "difficulty": "Medium",
        "key_vocabulary": ["curiosity", "glide", "dawn", "balanced", "sparked", "soar"]
    },
    {
        "id": "en-banyan-gr5",
        "title": "The Whispering Banyan Tree",
        "grade_level": 5,
        "language": "en",
        "target_wcpm": 95,
        "description": "An environmental story about an ancient banyan tree protecting a bird sanctuary.",
        "text": "At the edge of the sanctuary stood a magnificent banyan tree with aerial roots that touched the mossy ground. During the monsoon season, flock after flock of migratory storks nested among its dense green canopy. The village children gathered underneath its broad shade to hear elders recount legendary tales of courageous kings and wise travelers. When loggers arrived with loud machines, the entire community joined hands in peaceful unity to protect their sacred heritage.",
        "difficulty": "Challenging",
        "key_vocabulary": ["sanctuary", "magnificent", "aerial", "migratory", "canopy", "courageous", "heritage"]
    },
    {
        "id": "hi-rabbit-gr3",
        "title": "चालाक खरगोश और शेर",
        "grade_level": 3,
        "language": "hi",
        "target_wcpm": 60,
        "description": "पंचतंत्र की प्रसिद्ध कहानी जो चतुराई और बुद्धि का महत्व बताती है।",
        "text": "एक घने जंगल में भासुरक नाम का एक घमंडी शेर रहता था। वह प्रतिदिन कई निर्दोष जानवरों का शिकार करता था। एक दिन एक बुद्धिमान छोटे खरगोश की बारी आई। खरगोश ने एक गहरी योजना बनाई और शेर को एक गहरे कुएँ के पास ले गया। कुएँ के पानी में अपनी परछाई देखकर शेर ने गर्जना की और कुएँ में कूद पड़ा। इस तरह छोटे खरगोश ने अपनी सूझबूझ से जंगल के सभी जीवों की जान बचाई।",
        "difficulty": "Easy",
        "key_vocabulary": ["घमंडी", "बुद्धिमान", "परछाई", "गर्जना", "सूझबूझ"]
    },
    {
        "id": "hi-farmer-gr4",
        "title": "मेहनती किसान और सुनहरा खेत",
        "grade_level": 4,
        "language": "hi",
        "target_wcpm": 75,
        "description": "परिश्रम और ईमानदारी की प्रेरणादायक कहानी।",
        "text": "रामू काका गाँव के सबसे परिश्रमी किसान थे। वह सूरज उगने से पहले ही अपने दो बैलों के साथ खेत में पहुँच जाते थे। कड़ाके की धूप हो या मूसलाधार बारिश, उन्होंने कभी काम से जी नहीं चुराया। जब सुनहरी फसल लहलहाई, तो पूरे गाँव ने उनके धैर्य और लगन की प्रशंसा की। रामू काका ने सिखाया कि सच्ची मेहनत कभी व्यर्थ नहीं जाती।",
        "difficulty": "Medium",
        "key_vocabulary": ["परिश्रमी", "मूसलाधार", "धैर्य", "प्रशंसा", "व्यर्थ"]
    }
]

def get_all_passages(grade: Optional[int] = None, language: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve passages optionally filtered by grade level and language."""
    results = PASSAGES
    if grade is not None:
        results = [p for p in results if p["grade_level"] == grade]
    if language is not None:
        results = [p for p in results if p["language"].lower() == language.lower()]
    return results

def get_passage_by_id(passage_id: str) -> Optional[Dict[str, Any]]:
    """Find a specific passage by ID."""
    for p in PASSAGES:
        if p["id"] == passage_id:
            return p
    return None
