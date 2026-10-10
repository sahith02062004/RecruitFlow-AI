"""
Skill Normalization and Matching Component for RecruitFlow AI (Phase 5).
Ensures deterministic skill comparison, alias mapping, deduplication,
and strict distinction between distinct programming languages and tools (e.g., Java != JavaScript).
"""
import re
from typing import List, Set, Tuple, Dict, Union, Optional

# Canonical Alias Mapping (lowercase alias -> Canonical Display Name)
SKILL_ALIASES: Dict[str, str] = {
    # Languages
    "python": "Python",
    "python3": "Python",
    "py": "Python",
    "javascript": "JavaScript",
    "js": "JavaScript",
    "ecmascript": "JavaScript",
    "typescript": "TypeScript",
    "ts": "TypeScript",
    "java": "Java",
    "core java": "Java",
    "c++": "C++",
    "cpp": "C++",
    "c#": "C#",
    "csharp": "C#",
    "c sharp": "C#",
    "golang": "Go",
    "go language": "Go",
    "go": "Go",
    "rust": "Rust",
    "rustlang": "Rust",
    "php": "PHP",
    "php7": "PHP",
    "php8": "PHP",
    "ruby": "Ruby",
    "ruby on rails": "Ruby on Rails",
    "rails": "Ruby on Rails",
    "swift": "Swift",
    "swiftui": "SwiftUI",
    "kotlin": "Kotlin",
    "sql": "SQL",
    "t-sql": "SQL",
    "pl/sql": "SQL",
    "html": "HTML",
    "html5": "HTML",
    "css": "CSS",
    "css3": "CSS",
    "bash": "Bash/Shell",
    "shell": "Bash/Shell",
    "shell scripting": "Bash/Shell",
    "powershell": "Bash/Shell",

    # Frameworks & Libraries
    "flask": "Flask",
    "django": "Django",
    "fastapi": "FastAPI",
    "react": "React",
    "reactjs": "React",
    "react.js": "React",
    "angular": "Angular",
    "angularjs": "Angular",
    "vue": "Vue.js",
    "vuejs": "Vue.js",
    "vue.js": "Vue.js",
    "node": "Node.js",
    "nodejs": "Node.js",
    "node.js": "Node.js",
    "express": "Express.js",
    "expressjs": "Express.js",
    "express.js": "Express.js",
    "spring": "Spring Boot",
    "spring boot": "Spring Boot",
    "springboot": "Spring Boot",
    "asp.net": ".NET",
    "dotnet": ".NET",
    ".net": ".NET",
    ".net core": ".NET",
    "next.js": "Next.js",
    "nextjs": "Next.js",
    "bootstrap": "Bootstrap",
    "bootstrap 5": "Bootstrap",
    "tailwind": "Tailwind CSS",
    "tailwindcss": "Tailwind CSS",
    "tailwind css": "Tailwind CSS",
    "jquery": "jQuery",

    # Databases
    "mysql": "MySQL",
    "postgresql": "PostgreSQL",
    "postgres": "PostgreSQL",
    "psql": "PostgreSQL",
    "sqlite": "SQLite",
    "sqlite3": "SQLite",
    "mongodb": "MongoDB",
    "mongo": "MongoDB",
    "redis": "Redis",
    "elasticsearch": "Elasticsearch",
    "oracle database": "Oracle Database",
    "cassandra": "Cassandra",
    "dynamodb": "DynamoDB",

    # Cloud & DevOps
    "aws": "AWS",
    "amazon web services": "AWS",
    "azure": "Azure",
    "microsoft azure": "Azure",
    "gcp": "Google Cloud",
    "google cloud": "Google Cloud",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "k8s": "Kubernetes",
    "ci/cd": "CI/CD",
    "cicd": "CI/CD",
    "git": "Git",
    "github actions": "GitHub Actions",
    "terraform": "Terraform",
    "linux": "Linux",
    "nginx": "Nginx",
    "jenkins": "Jenkins",

    # AI / ML
    "machine learning": "Machine Learning",
    "deep learning": "Deep Learning",
    "pytorch": "PyTorch",
    "tensorflow": "TensorFlow",
    "scikit-learn": "Scikit-Learn",
    "scikit learn": "Scikit-Learn",
    "sklearn": "Scikit-Learn",
    "pandas": "Pandas",
    "numpy": "NumPy",
    "nlp": "NLP",
    "langchain": "LangChain",
    "hugging face": "Hugging Face",
    "huggingface": "Hugging Face",
    "computer vision": "Computer Vision",
    "llm": "LLM",
    "generative ai": "Generative AI",

    # Architecture & Tools
    "rest api": "REST API",
    "rest apis": "REST API",
    "restful": "REST API",
    "restful api": "REST API",
    "graphql": "GraphQL",
    "agile": "Agile",
    "scrum": "Scrum",
    "jira": "Jira",
    "microservices": "Microservices",
    "system design": "System Design",
    "unit testing": "Unit Testing",
    "pytest": "Unit Testing",
}


class SkillNormalizer:
    """Provides skill string parsing, canonical normalization, and exact comparison."""

    @classmethod
    def normalize_single_skill(cls, skill: str) -> Optional[str]:
        """
        Normalizes a single skill string:
        - Trims whitespace.
        - Resolves through controlled alias dictionary.
        - Preserves title case for unrecognized skills while trimming.
        """
        if not skill or not isinstance(skill, str):
            return None

        cleaned = skill.strip()
        if not cleaned:
            return None

        lower = cleaned.lower()
        if lower in SKILL_ALIASES:
            return SKILL_ALIASES[lower]

        # Normalize capitalization for unmapped custom skills
        # Don't capitalize all-caps acronyms (e.g. AWS, CI/CD, SQL)
        if cleaned.isupper() and len(cleaned) <= 5:
            return cleaned

        return cleaned.title()

    @classmethod
    def parse_skills_input(cls, raw_input: Union[str, List[str], Set[str], None]) -> List[str]:
        """
        Parses raw skill inputs from string (comma, newline, pipe, semicolon separated)
        or list/set, deduplicates, and normalizes.
        """
        if not raw_input:
            return []

        if isinstance(raw_input, (list, set, tuple)):
            tokens = list(raw_input)
        elif isinstance(raw_input, str):
            # Split by comma, newline, semicolon, or bullet points
            tokens = re.split(r"[,;\n\r\|•]+", raw_input)
        else:
            return []

        normalized_skills: List[str] = []
        seen_keys: Set[str] = set()

        for token in tokens:
            norm = cls.normalize_single_skill(token)
            if norm:
                # Key for deduplication (case-insensitive)
                key = norm.lower()
                if key not in seen_keys:
                    seen_keys.add(key)
                    normalized_skills.append(norm)

        return sorted(normalized_skills)

    @classmethod
    def match_skills(
        cls,
        candidate_skills: Union[str, List[str]],
        target_skills: Union[str, List[str]]
    ) -> Tuple[List[str], List[str]]:
        """
        Compares normalized candidate skills against normalized target requirements.
        Returns (matched_skills_list, missing_skills_list).

        Strictly prevents substring false positives (e.g., 'Java' will NOT match 'JavaScript',
        'C' will NOT match 'C++', 'Go' will NOT match 'Google Cloud').
        """
        cand_list = cls.parse_skills_input(candidate_skills)
        target_list = cls.parse_skills_input(target_skills)

        # Build candidate lookup dictionary of lower_skill -> canonical_skill
        cand_lookup = {s.lower(): s for s in cand_list}

        matched: List[str] = []
        missing: List[str] = []

        for target in target_list:
            target_key = target.lower()
            if target_key in cand_lookup:
                matched.append(target)
            else:
                missing.append(target)

        return sorted(matched), sorted(missing)
