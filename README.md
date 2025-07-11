# ScoreSight API

A cloud-ready FastAPI service for automated exam grading and analysis using AI. This service converts the Jupyter notebook analysis workflow into a scalable backend service with Redis/Celery for background processing.

## Features

- **PDF Processing**: Upload PDF exams and split into pages for analysis
- **AI-Powered Transcription**: Extract exam questions, answers, and grading using OpenAI GPT models
- **Page Range Selection**: Process specific page ranges (start_page to end_page)
- **Asynchronous Processing**: Background job processing with Celery
- **Misconception Analysis**: Identify common student misconceptions using AI
- **Multiple Export Formats**: CSV for transcription, Excel for analysis reports
- **Real-time Job Tracking**: Monitor processing progress and status

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   FastAPI       │    │   Background    │
│   Client        │───▶│   API Server    │───▶│   Workers       │
└─────────────────┘    └─────────────────┘    │   (Celery)      │
                                              └─────────────────┘
                                                      │
                                              ┌─────────────────┐
                                              │   Redis         │
                                              │   (Broker)      │
                                              └─────────────────┘
```

## Quick Start

### 1. Environment Setup

```bash
# Copy environment file and configure
cp .env.example .env
# Edit .env with your OpenAI API key and other settings

# Install dependencies
make install

# Initialize database
make db-init
```

### 2. Start Services

```bash
# Terminal 1: Start Redis
make db

# Terminal 2: Start API server
make run

# Terminal 3: Start Celery workers
make celery
```

### 3. API Usage

The API will be available at `http://localhost:8000`

- API Documentation: `http://localhost:8000/docs`
- Health Check: `http://localhost:8000/health`

## API Endpoints

### Exam Management

#### Create Exam Type
```http
POST /api/v1/exams/types/
{
  "name": "MIDTERM",
  "description": "Mid-term examination"
}
```

#### Create Exam
```http
POST /api/v1/exams/
{
  "title": "Mathematics Midterm",
  "subject": "Mathematics",
  "class_name": "Grade 10A",
  "exam_type_id": 1
}
```

### PDF Processing

#### Upload and Process PDF
```http
POST /api/v1/exams/uploads/pdf/
Content-Type: multipart/form-data

- file: [PDF file]
- exam_id: 1 (optional)
- start_page: 1 (optional, default: 1)
- end_page: 10 (optional, default: all pages)
- class_name: "Grade 10A" (optional)
- subject_name: "Mathematics" (optional)
```

**Response:**
```json
{
  "job_ids": ["550e8400-e29b-41d4-a716-446655440000"],
  "upload_ids": [1],
  "status": "queued",
  "message": "Processing 1 PDF(s) from page 1 to 10"
}
```

### Job Monitoring

#### Get Job Status
```http
GET /api/v1/exams/jobs/{job_id}
```

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "PROCESSING",
  "progress": {
    "current": 5,
    "total": 10,
    "status": "Analyzing page 5 (5 of 10)..."
  }
}
```

#### List All Jobs
```http
GET /api/v1/exams/jobs/
```

### Results and Downloads

#### Download Transcription Results (CSV)
```http
GET /api/v1/exams/download/transcription/{job_id}
```

#### Download Analysis Results (Excel)
```http
GET /api/v1/exams/download/analysis/{job_id}
```

#### Get Exam Analysis
```http
GET /api/v1/exams/analysis/{exam_id}
```

## Processing Workflow

1. **PDF Upload**: Client uploads PDF with optional parameters
2. **Job Creation**: System creates background job and returns job ID
3. **Page Splitting**: PDF is split into individual page images
4. **AI Analysis**: Each page is sent to OpenAI for transcription
5. **Data Processing**: Results are cleaned and standardized
6. **Misconception Analysis**: AI analyzes common student errors
7. **Report Generation**: Creates CSV (transcription) and Excel (analysis) files
8. **Completion**: Files available for download via job ID

## Data Flow

```
PDF Upload → Page Splitting → AI Transcription → Data Cleaning → Analysis → Report Generation
     ↓              ↓              ↓              ↓           ↓           ↓
   Job ID      Page Images    JSON Results    CSV Data    Analysis    Excel Report
```

## Key Features from Notebook

The API replicates all major functionality from the Jupyter notebook:

- ✅ PDF page splitting and image extraction
- ✅ OpenAI GPT-4 image analysis with fine-tuned prompts
- ✅ Student name tracking across pages
- ✅ Question number standardization
- ✅ Grading classification (Correct/Incorrect/Not Graded)
- ✅ Misconception detection using AI
- ✅ Statistical analysis and reporting
- ✅ Excel export with multiple sheets

## Environment Variables

```bash
# Required
OPENAI_API_KEY=your_openai_api_key_here

# Optional (with defaults)
OPENAI_MODEL=gpt-4o-mini
DATABASE_URL=sqlite:///scoresight/database/scoresight.db
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
```

## Error Handling

The API includes comprehensive error handling:

- Invalid file formats return 400 errors
- Missing files return 404 errors
- Processing failures are captured in job status
- Partial results are saved even if some pages fail

## Monitoring

- Use `/api/v1/exams/jobs/` to monitor all active jobs
- Check `/api/v1/exams/workers/` for worker status
- Individual job progress via `/api/v1/exams/jobs/{job_id}`

## Development

```bash
# Run tests
make test

# Code formatting
make lint

# Database migrations
make db-migrate msg="Add new field"
make db-upgrade
```

## Deployment

For production deployment:

1. Use a proper database (PostgreSQL recommended)
2. Configure Redis for production
3. Use multiple Celery workers
4. Set up proper logging and monitoring
5. Use environment-specific configuration

## Testing

The service can be tested using the included test files:

```bash
# API tests
python -m pytest tests/api/ -v

# Unit tests
python -m pytest tests/unit/ -v
```

Example test files are available for testing the core functionality.
