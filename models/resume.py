from dataclasses import dataclass, field


@dataclass
class PersonalInfo:
    name: str
    email: str = ""
    phone: str = ""
    github: str = ""
    linkedin: str = ""


@dataclass
class Education:
    degree: str
    institution: str
    location: str = ""
    date: str = ""
    description: str = ""


@dataclass
class WorkExperience:
    title: str
    company: str
    location: str = ""
    period: str = ""
    description: str = ""
    skills: list[str] = field(default_factory=list)


@dataclass
class Project:
    name: str
    description: str = ""
    technologies: list[str] = field(default_factory=list)
    url: str = ""


@dataclass
class Skills:
    hard: list[str] = field(default_factory=list)
    soft: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)


@dataclass
class Resume:
    personal_info: PersonalInfo
    education: list[Education] = field(default_factory=list)
    work_experience: list[WorkExperience] = field(default_factory=list)
    projects: list[Project] = field(default_factory=list)
    skills: Skills = field(default_factory=Skills)
    raw_text: str = ""
