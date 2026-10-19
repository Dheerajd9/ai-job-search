import json
from pathlib import Path

FIX = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def profile(**over):
    p = {
        "contact": {"first_name": "Test", "last_name": "Person", "email": "test@example.com",
                    "phone": "+1 614 555 0100", "city": "Columbus", "region": "OH", "country": "United States",
                    "linkedin": "https://linkedin.com/in/test", "github": "", "portfolio": "", "current_company": ""},
        "headline": "Data / MLOps Engineer",
        "skills": ["Python", "PySpark", "SQL", "Databricks", "Azure", "Kubernetes", "Terraform", "Kafka", "Airflow", "Docker"],
        "certifications": [{"name": "Databricks Data Engineer Associate", "issuer": "Databricks", "date": "2024-01"}],
        "education": [{"degree": "MS Computer Information Systems", "school": "Some University", "location": "NH, USA",
                       "start": "2021-01", "end": "2022-09", "gpa": "3.7"}],
        "experience": [
            {"id": "j1", "title": "Big Data SQL Developer", "company": "Bank Co", "location": "Irving, TX",
             "start": "2024-11", "end": "2025-12",
             "bullets": [{"id": "j1-a", "text": "Built PySpark pipelines processing 2 TB daily, cutting runtime by 35%."},
                         {"id": "j1-b", "text": "Migrated 40 SQL jobs to Databricks workflows."},
                         {"id": "j1-c", "text": "Automated data quality checks with Great Expectations."}]},
            {"id": "j2", "title": "Data Engineer", "company": "Health Co", "location": "Remote",
             "start": "2023-06", "end": "2023-11",
             "bullets": [{"id": "j2-a", "text": "Designed HIPAA-compliant ingestion on Azure Data Factory."}]},
        ],
        "work_authorization": {"us": {"authorized": True, "needs_sponsorship": False},
                               "ca": {"authorized": None, "needs_sponsorship": None},
                               "in": {"authorized": True, "needs_sponsorship": False}},
        "salary_expectation": {"us": "", "ca": "", "in": ""},
        "notice_period": "Immediately available", "willing_to_relocate": True, "pronouns": "",
        "eeo_policy": "decline", "accept_application_privacy_consent": False,
        "answers": [{"match": "how did you (hear|find|learn)", "answer": "Company careers page"},
                    {"match": "kubeflow", "answer": "No"}],
    }
    p.update(over)
    return p


CFG = {
    "roles": {
        "data_engineer": [r"\bdata engineer", r"\bbig data\b"],
        "data_analyst": [r"\bdata analyst"],
        "data_center": [r"\bdata ?cent(er|re)\b"],
        "ai_engineer": [r"\bai engineer"],
        "forward_deployed": [r"\bforward[- ]deployed"],
        "mlops": [r"\bmlops\b"],
    },
    "exclude_title": [r"\bintern(ship)?\b", r"\bmanager\b"],
    "countries": {
        "us": {"enabled": True, "locations": ["remote - us", "united states", "ohio", "columbus", "dayton"], "accept_plain_remote": True},
        "ca": {"enabled": True, "locations": ["canada", "toronto", "vancouver"], "accept_plain_remote": False},
        "in": {"enabled": True, "locations": ["india", "hyderabad", "bengaluru"], "accept_plain_remote": False},
    },
    "boards": {},
    "posted_within_days": 7,
}
