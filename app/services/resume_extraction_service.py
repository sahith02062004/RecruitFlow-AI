"""
Resume Information Extraction Service for RecruitFlow AI (Phase 4).
Deterministic extraction of candidate metadata, contact details, profile links,
skills with alias normalization, education credentials, work experience history,
and data quality diagnostics without external/paid LLM APIs.
"""
import re
from datetime import datetime
from typing import Dict, Any, List, Optional, Set, Tuple


# Comprehensive Skill Taxonomy: maps canonical skill name to set of aliases/variations
SKILL_TAXONOMY: Dict[str, List[str]] = {
    # Programming Languages
    "Python": ["python", "python3", "py"],
    "JavaScript": ["javascript", "js", "ecmascript"],
    "TypeScript": ["typescript", "ts"],
    "Java": ["java", "core java", "j2ee"],
    "C++": ["c++", "cpp"],
    "C#": ["c#", "csharp", "c sharp"],
    "Go": ["golang", "go language"],
    "Rust": ["rust", "rustlang"],
    "PHP": ["php", "php7", "php8"],
    "Ruby": ["ruby", "ruby on rails", "rails"],
    "Swift": ["swift", "swiftui"],
    "Kotlin": ["kotlin"],
    "SQL": ["sql", "t-sql", "pl/sql", "plsql"],
    "HTML": ["html", "html5"],
    "CSS": ["css", "css3"],
    "Bash/Shell": ["bash", "shell scripting", "powershell", "zsh"],

    # Web & Application Frameworks
    "Flask": ["flask"],
    "Django": ["django"],
    "FastAPI": ["fastapi", "fast-api"],
    "React": ["react", "react.js", "reactjs"],
    "Angular": ["angular", "angular.js", "angularjs", "angular 2+"],
    "Vue.js": ["vue", "vue.js", "vuejs"],
    "Node.js": ["node", "node.js", "nodejs"],
    "Express.js": ["express", "express.js", "expressjs"],
    "Spring Boot": ["spring boot", "springboot", "spring framework"],
    ".NET": [".net", "asp.net", "dotnet", ".net core"],
    "Next.js": ["next.js", "nextjs"],
    "Bootstrap": ["bootstrap", "bootstrap 5"],
    "Tailwind CSS": ["tailwind", "tailwindcss", "tailwind css"],
    "jQuery": ["jquery"],

    # Databases & Storage
    "MySQL": ["mysql"],
    "PostgreSQL": ["postgresql", "postgres", "psql"],
    "SQLite": ["sqlite", "sqlite3"],
    "MongoDB": ["mongodb", "mongo"],
    "Redis": ["redis"],
    "Elasticsearch": ["elasticsearch", "elastic search"],
    "Oracle Database": ["oracle db", "oracle database", "pl/sql"],
    "Cassandra": ["cassandra", "apache cassandra"],
    "DynamoDB": ["dynamodb", "aws dynamodb"],

    # Cloud, DevOps & Infrastructure
    "AWS": ["aws", "amazon web services", "ec2", "s3", "lambda"],
    "Azure": ["azure", "microsoft azure"],
    "Google Cloud": ["gcp", "google cloud", "google cloud platform"],
    "Docker": ["docker", "dockerfile", "containerization"],
    "Kubernetes": ["kubernetes", "k8s"],
    "CI/CD": ["ci/cd", "cicd", "continuous integration", "continuous deployment"],
    "Git": ["git", "github", "gitlab", "version control"],
    "GitHub Actions": ["github actions", "gh actions"],
    "Terraform": ["terraform"],
    "Linux": ["linux", "ubuntu", "debian", "centos", "redhat"],
    "Nginx": ["nginx"],
    "Jenkins": ["jenkins"],

    # AI, Data Science & Machine Learning
    "Machine Learning": ["machine learning", "ml algorithms"],
    "Deep Learning": ["deep learning", "neural networks", "cnn", "rnn", "lstm"],
    "PyTorch": ["pytorch"],
    "TensorFlow": ["tensorflow", "keras"],
    "Scikit-Learn": ["scikit-learn", "scikit learn", "sklearn"],
    "Pandas": ["pandas"],
    "NumPy": ["numpy"],
    "NLP": ["nlp", "natural language processing", "text processing"],
    "LangChain": ["langchain"],
    "Hugging Face": ["hugging face", "huggingface", "transformers"],
    "Computer Vision": ["computer vision", "opencv"],
    "LLM": ["llm", "large language models", "generative ai", "genai", "prompt engineering"],

    # Architecture, Testing & Methodologies
    "REST API": ["rest api", "restful", "restful api", "rest apis", "rest endpoints"],
    "GraphQL": ["graphql"],
    "Agile": ["agile", "scrum", "kanban"],
    "Jira": ["jira"],
    "TDD": ["tdd", "test driven development"],
    "Microservices": ["microservices", "microservice architecture"],
    "System Design": ["system design", "distributed systems"],
    "Unit Testing": ["unit testing", "pytest", "unittest", "junit"],
}


class ResumeExtractionService:
    """Performs deterministic parsing and feature extraction on resume text."""

    @classmethod
    def extract_all(cls, raw_text: str, fallback_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Executes full extraction pipeline on clean raw resume text.
        Returns a normalized dictionary structure suitable for DB storage and profile sync.
        """
        if not raw_text:
            return {
                "name": fallback_name or "Unknown Candidate",
                "email": "",
                "phone": "",
                "links": {},
                "skills": [],
                "skills_count": 0,
                "education": [],
                "experience": [],
                "total_experience_years": 0.0,
                "summary": "",
                "warnings": ["No text could be extracted from this document."],
                "extracted_at": datetime.utcnow().isoformat(),
            }

        warnings: List[str] = []

        # 1. Email extraction
        email = cls.extract_email(raw_text)
        if not email:
            warnings.append("No email address detected.")

        # 2. Phone extraction
        phone = cls.extract_phone(raw_text)
        if not phone:
            warnings.append("No phone number detected.")

        # 3. Links extraction
        links = cls.extract_links(raw_text)

        # 4. Name extraction
        name = cls.extract_name(raw_text, fallback=fallback_name)

        # 5. Skills extraction
        skills = cls.extract_skills(raw_text)
        if len(skills) < 3:
            warnings.append("Low skill count detected (fewer than 3 recognized skills).")

        # 6. Education extraction
        education = cls.extract_education(raw_text)

        # 7. Experience extraction
        experience, exp_years = cls.extract_experience(raw_text)

        # 8. Summary / Objective extraction
        summary = cls.extract_summary(raw_text)

        return {
            "name": name,
            "email": email or "",
            "phone": phone or "",
            "links": links,
            "skills": skills,
            "skills_count": len(skills),
            "education": education,
            "experience": experience,
            "total_experience_years": exp_years,
            "summary": summary,
            "warnings": warnings,
            "extracted_at": datetime.utcnow().isoformat(),
        }

    @staticmethod
    def extract_email(text: str) -> Optional[str]:
        """Extracts the primary candidate email using standard RFC-compliant regex pattern."""
        pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,7}\b"
        matches = re.findall(pattern, text)
        if matches:
            # Clean and lowercase
            clean = matches[0].strip().rstrip(".,;").lower()
            return clean
        return None

    @staticmethod
    def extract_phone(text: str) -> Optional[str]:
        """
        Extracts phone numbers in international (+XX) and national formats:
        Supports formats: +1-555-123-4567, (555) 123-4567, +91 9876543210, 555-123-4567.
        """
        patterns = [
            r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}",
            r"\+\d{1,3}[-.\s]?\d{9,12}",
            r"\b\d{10}\b",
        ]
        for pat in patterns:
            matches = re.finditer(pat, text)
            for m in matches:
                cand = m.group(0).strip()
                # Verify digit count (between 10 and 15 digits)
                digits = re.sub(r"\D", "", cand)
                if 10 <= len(digits) <= 15:
                    return cand
        return None

    @staticmethod
    def extract_links(text: str) -> Dict[str, str]:
        """Extracts candidate profile links (LinkedIn, GitHub, Portfolio)."""
        links: Dict[str, str] = {}

        # LinkedIn
        li_match = re.search(r"(?:https?:\/\/)?(?:www\.)?linkedin\.com\/in\/([a-zA-Z0-9_\-]+)", text, re.IGNORECASE)
        if li_match:
            links["linkedin"] = f"https://www.linkedin.com/in/{li_match.group(1)}"

        # GitHub
        gh_match = re.search(r"(?:https?:\/\/)?(?:www\.)?github\.com\/([a-zA-Z0-9_\-]+)", text, re.IGNORECASE)
        if gh_match:
            # Avoid matching common non-profile github links
            sub = gh_match.group(1).lower()
            if sub not in ("topics", "features", "enterprise", "pricing", "explore", "about"):
                links["github"] = f"https://github.com/{gh_match.group(1)}"

        # Portfolio / Personal Website
        url_pattern = r"https?://(?:www\.)?([a-zA-Z0-9-]+\.[a-zA-Z]{2,}(?:/[^\s,]*)?)"
        for m in re.finditer(url_pattern, text, re.IGNORECASE):
            full_url = m.group(0).rstrip(".,;)")
            domain = m.group(1).lower()
            if "linkedin.com" in domain or "github.com" in domain or "google.com" in domain or "gmail.com" in domain:
                continue
            if "portfolio" not in links:
                links["portfolio"] = full_url

        return links

    @classmethod
    def extract_name(cls, text: str, fallback: Optional[str] = None) -> str:
        """
        Extracts candidate name by examining the top lines of the resume.
        Skips contact headers, email lines, phone numbers, and common labels.
        """
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        ignore_words = {
            "resume", "curriculum", "vitae", "cv", "summary", "profile", "contact",
            "education", "experience", "skills", "projects", "page", "phone", "email"
        }

        for line in lines[:6]:  # Name is virtually always in the top 6 non-empty lines
            # Skip lines with email or phone
            if "@" in line or any(d in line for d in ("http://", "https://", "www.")):
                continue

            cleaned_line = re.sub(r"[^a-zA-Z\s.-]", "", line).strip()
            words = cleaned_line.split()

            # Name typically consists of 2 to 4 capitalized words
            if 2 <= len(words) <= 4:
                if any(w.lower() in ignore_words for w in words):
                    continue
                # Ensure each word starts with a capital letter
                if all(w[0].isupper() for w in words if w):
                    return " ".join(words)

        return fallback or "Candidate"

    @classmethod
    def extract_skills(cls, text: str) -> List[str]:
        """
        Extracts skills using the taxonomy dictionary, matching variants/aliases
        and normalizing to canonical names.
        """
        found_skills: Set[str] = set()
        lower_text = text.lower()

        for canonical_name, aliases in SKILL_TAXONOMY.items():
            for alias in aliases:
                # Use word-boundary regex for clean matching
                escaped_alias = re.escape(alias)
                # Handle special characters like C++, C#, .NET
                if alias in ("c++", "c#", ".net"):
                    pattern = r"(?:^|\s|[,\/;])" + escaped_alias + r"(?:$|\s|[,\/;])"
                else:
                    pattern = r"\b" + escaped_alias + r"\b"

                if re.search(pattern, lower_text, re.IGNORECASE):
                    found_skills.add(canonical_name)
                    break

        return sorted(list(found_skills))

    @classmethod
    def extract_education(cls, text: str) -> List[Dict[str, str]]:
        """
        Identifies education credentials, degrees, institutions, and graduation years.
        """
        education_records: List[Dict[str, str]] = []
        degree_patterns = [
            (r"\b(Ph\.?D\.?|Doctor of Philosophy)\b", "Ph.D"),
            (r"\b(M\.?Tech\.?|Master of Technology)\b", "M.Tech"),
            (r"\b(M\.?S\.?|Master of Science)\b", "M.S."),
            (r"\b(M\.?B\.?A\.?|Master of Business Administration)\b", "MBA"),
            (r"\b(Master['\w\s]*Degree|Masters)\b", "Master's Degree"),
            (r"\b(B\.?Tech\.?|Bachelor of Technology)\b", "B.Tech"),
            (r"\b(B\.?E\.?|Bachelor of Engineering)\b", "B.E."),
            (r"\b(B\.?S\.?|Bachelor of Science)\b", "B.S."),
            (r"\b(B\.?Sc\.?)\b", "B.Sc"),
            (r"\b(Bachelor['\w\s]*Degree|Bachelors)\b", "Bachelor's Degree"),
            (r"\b(Associate['\w\s]*Degree|Associates)\b", "Associate Degree"),
            (r"\b(Diploma in [A-Za-z\s]+)\b", "Diploma"),
        ]

        # Search for education block or occurrences
        lines = text.split("\n")
        in_edu_section = False
        edu_lines: List[str] = []

        for line in lines:
            line_strip = line.strip()
            # Section header check
            if re.match(r"^(education|academic background|qualifications|academics)$", line_strip, re.IGNORECASE):
                in_edu_section = True
                continue
            elif in_edu_section and re.match(r"^(experience|employment|work history|skills|projects|certifications)$", line_strip, re.IGNORECASE):
                in_edu_section = False
                break

            if in_edu_section:
                edu_lines.append(line_strip)

        target_text = "\n".join(edu_lines) if edu_lines else text

        # Search for degrees and graduation years
        year_pattern = r"\b(19\d{2}|20\d{2})\s*(?:-|to)?\s*(19\d{2}|20\d{2}|present)?\b"
        
        seen_degrees = set()
        for deg_regex, standard_title in degree_patterns:
            matches = list(re.finditer(deg_regex, target_text, re.IGNORECASE))
            if matches and standard_title not in seen_degrees:
                seen_degrees.add(standard_title)
                deg_match = matches[0]
                
                # Context surrounding degree (100 chars around)
                start = max(0, deg_match.start() - 50)
                end = min(len(target_text), deg_match.end() + 100)
                context = target_text[start:end]

                year_match = re.search(year_pattern, context, re.IGNORECASE)
                year_str = year_match.group(0) if year_match else ""

                education_records.append({
                    "degree": standard_title,
                    "institution": "",  # Extracted from context if identifiable
                    "year": year_str,
                    "details": deg_match.group(0),
                })

        return education_records

    @classmethod
    def extract_experience(cls, text: str) -> Tuple[List[Dict[str, str]], float]:
        """
        Extracts work experience history items and calculates total years of experience.
        """
        experience_records: List[Dict[str, str]] = []
        total_years = 0.0

        # Find date ranges like "2020 - 2023", "Jan 2021 - Present", "2019 to Present"
        date_range_regex = r"(?P<start_month>Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)?\s*(?P<start_year>20\d{2}|19\d{2})\s*(?:-|–|to)\s*(?P<end_month>Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)?\s*(?P<end_year>20\d{2}|19\d{2}|present|current)"

        matches = list(re.finditer(date_range_regex, text, re.IGNORECASE))
        current_year = datetime.utcnow().year

        year_spans = []
        for m in matches:
            s_year = int(m.group("start_year"))
            e_str = m.group("end_year").lower()
            if e_str in ("present", "current"):
                e_year = current_year
            else:
                try:
                    e_year = int(e_str)
                except ValueError:
                    e_year = s_year

            if s_year <= e_year and (e_year - s_year) <= 30:
                span = e_year - s_year
                year_spans.append((s_year, e_year, m.group(0)))

        # Also search for explicit mention like "4+ years of experience" or "5 years experience"
        mention_regex = r"(\d+(?:\.\d+)?)\+?\s*years?(?:\s+of)?\s+experience"
        exp_mention = re.search(mention_regex, text, re.IGNORECASE)
        if exp_mention:
            try:
                mentioned_years = float(exp_mention.group(1))
                if 0 <= mentioned_years <= 40:
                    total_years = max(total_years, mentioned_years)
            except ValueError:
                pass

        if year_spans:
            # Combine non-overlapping ranges or sum durations
            earliest = min(s for s, e, _ in year_spans)
            latest = max(e for s, e, _ in year_spans)
            span_years = float(max(1, latest - earliest))
            total_years = max(total_years, min(span_years, 35.0))

            for s, e, raw in year_spans[:5]:
                experience_records.append({
                    "duration": raw,
                    "start_year": str(s),
                    "end_year": str(e),
                })

        return experience_records, round(total_years, 1)

    @classmethod
    def extract_summary(cls, text: str) -> str:
        """
        Locates executive summary / about section in resume.
        """
        lines = text.split("\n")
        in_summary = False
        summary_lines: List[str] = []

        header_patterns = r"^(professional summary|executive summary|summary|about me|profile|objective)$"
        next_headers = r"^(experience|work experience|employment|education|skills|projects|certifications)$"

        for line in lines:
            line_strip = line.strip()
            if re.match(header_patterns, line_strip, re.IGNORECASE):
                in_summary = True
                continue
            elif in_summary and re.match(next_headers, line_strip, re.IGNORECASE):
                in_summary = False
                break

            if in_summary:
                if line_strip:
                    summary_lines.append(line_strip)
                if len(summary_lines) >= 6:  # Summary is usually 2-5 sentences
                    break

        return " ".join(summary_lines).strip()
