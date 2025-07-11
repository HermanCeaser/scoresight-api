from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional, List
from datetime import datetime


# ExamType schemas
class ExamTypeBase(BaseModel):
    name: str  # Changed from enum to string
    description: Optional[str] = None


class ExamTypeCreate(ExamTypeBase):
    pass


class ExamTypeUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class ExamType(ExamTypeBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


# Exam schemas
class ExamBase(BaseModel):
    name: str  # Changed from title to name
    subject_name: Optional[str] = None  # Made optional
    class_name: Optional[str] = None    # Made optional
    exam_type_id: int
    description: Optional[str] = None
    scheduled_date: Optional[datetime] = None


class ExamCreate(ExamBase):
    pass


class ExamUpdate(BaseModel):
    name: Optional[str] = None
    subject_name: Optional[str] = None
    class_name: Optional[str] = None
    exam_type_id: Optional[int] = None
    description: Optional[str] = None
    scheduled_date: Optional[datetime] = None


class Exam(ExamBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime]
    exam_type: Optional[ExamType] = None

    class Config:
        from_attributes = True


class UploadCreate(BaseModel):
    exam_id: int
    filename: str
    start_page: Optional[int] = 1
    end_page: Optional[int] = None


class Upload(BaseModel):
    id: int
    exam_id: int
    filename: str
    status: str
    start_page: Optional[int] = 1
    end_page: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class Report(BaseModel):
    id: int
    exam_id: int
    report_type: str
    file_path: str
    created_at: datetime

    class Config:
        from_attributes = True


# PDF Processing schemas
class PDFProcessRequest(BaseModel):
    exam_id: Optional[int] = None
    start_page: Optional[int] = 1
    end_page: Optional[int] = None
    class_name: Optional[str] = None
    subject_name: Optional[str] = None


class ProcessingJobResponse(BaseModel):
    job_id: str
    status: str
    message: Optional[str] = None


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: Optional[dict] = None
    result: Optional[dict] = None
    error: Optional[str] = None


# Transcription result schemas
class TranscriptionEntry(BaseModel):
    questionNo: str
    question: str
    answer: str
    grading: str


class TranscriptionResult(BaseModel):
    studentName: str
    entries: List[TranscriptionEntry]


class AnalysisResult(BaseModel):
    main_question_no: str
    question: str
    sub_question_no: str
    attempts: int
    distinct_students: int
    correct_answers: int
    correct_percentage: str
    most_common_misconception: Optional[str]
    misconception_frequency: int
