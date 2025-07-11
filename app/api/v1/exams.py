from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import os
import uuid
import shutil
import zipfile
import pandas as pd
import logging
from ...core.pdf_utils import split_pdf_to_pages, encode_image_to_base64, save_image
from ...core.openai_client import OpenAIClient
from ...core.analysis import analyse_results, analyze_misconceptions, clean_question_list
from ...schemas import ExamCreate, ExamUpdate, Exam, Upload, Report, ExamTypeCreate, ExamTypeUpdate, ExamType, PDFProcessRequest, ProcessingJobResponse, JobStatusResponse
from ...models import Exam as ExamModel, Upload as UploadModel, Report as ReportModel, ExamType as ExamTypeModel
from ...deps import get_db, Settings, get_settings
from ...tasks import process_pdf_task, generate_analysis_report, categorize_questions_task
from ...celery_app import celery_app
from fastapi.responses import StreamingResponse
import time

# Configure logging for this module
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

router = APIRouter()

@router.get("/health")
def health_check():
    """
    Health check endpoint to verify API and Celery connectivity.
    """
    logger.info("=== HEALTH CHECK ===")
    
    health_status = {
        "api": "healthy",
        "celery": {
            "broker_connected": False,
            "workers_available": False,
            "worker_count": 0,
            "registered_tasks": [],
            "broker_url": None,
            "result_backend": None,
            "errors": []
        },
        "timestamp": time.time()
    }
    
    try:
        # Get settings to show what broker we're trying to connect to
        from ...deps import get_settings
        settings = get_settings()
        health_status["celery"]["broker_url"] = settings.CELERY_BROKER_URL
        health_status["celery"]["result_backend"] = settings.CELERY_RESULT_BACKEND
        logger.info(f"Broker URL: {settings.CELERY_BROKER_URL}")
        logger.info(f"Result backend: {settings.CELERY_RESULT_BACKEND}")
        
        # Test Celery broker connectivity
        logger.info("Testing Celery broker connectivity...")
        inspect = celery_app.control.inspect()
        
        # Test basic inspect functionality
        stats = inspect.stats()
        logger.info(f"Worker stats result: {stats}")
        
        if stats:
            health_status["celery"]["broker_connected"] = True
            health_status["celery"]["workers_available"] = True
            health_status["celery"]["worker_count"] = len(stats)
            logger.info(f"Celery broker connected, {len(stats)} workers found")
            
            # Get registered tasks for each worker
            registered = inspect.registered()
            logger.info(f"Registered tasks result: {registered}")
            if registered:
                all_tasks = []
                for worker, tasks in registered.items():
                    all_tasks.extend(tasks)
                health_status["celery"]["registered_tasks"] = list(set(all_tasks))
        else:
            health_status["celery"]["errors"].append("No workers found")
            logger.warning("No workers found - this means either:")
            logger.warning("1. No Celery workers are running")
            logger.warning("2. Workers can't connect to the broker")
            logger.warning("3. Workers are connected to a different broker")
            
    except Exception as e:
        error_msg = f"Celery connectivity error: {str(e)}"
        health_status["celery"]["errors"].append(error_msg)
        logger.error(error_msg)
        logger.error(f"This usually means the broker (Redis/RabbitMQ) is not running or not accessible")
    
    logger.info(f"Health check complete: {health_status}")
    return health_status


@router.get("/celery/ping")
def ping_workers():
    """
    Ping Celery workers to test connectivity.
    """
    logger.info("=== PING WORKERS ===")
    
    try:
        # Try to ping workers
        inspect = celery_app.control.inspect()
        ping_result = inspect.ping()
        logger.info(f"Ping result: {ping_result}")
        
        if ping_result:
            return {
                "status": "success",
                "workers_responding": len(ping_result),
                "responses": ping_result
            }
        else:
            return {
                "status": "no_workers",
                "message": "No workers responded to ping",
                "workers_responding": 0,
                "responses": {}
            }
            
    except Exception as e:
        logger.error(f"Ping failed: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "workers_responding": 0
        }


@router.post("/celery/test-task")
def test_simple_task():
    """
    Create a simple test task to verify Celery is working.
    """
    logger.info("=== TEST SIMPLE TASK ===")
    
    try:
        # Send a simple test task
        result = celery_app.send_task('celery.ping')
        logger.info(f"Test task sent with ID: {result.id}")
        
        return {
            "status": "task_sent",
            "task_id": result.id,
            "message": "Test task sent successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to send test task: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "message": "Failed to send test task"
        }

# Exam Type endpoints
@router.post("/types/", response_model=ExamType)
def create_exam_type(exam_type_in: ExamTypeCreate, db: Session = Depends(get_db)):
    exam_type = ExamTypeModel(**exam_type_in.dict())
    db.add(exam_type)
    db.commit()
    db.refresh(exam_type)
    return exam_type

@router.get("/types/", response_model=List[ExamType])
def list_exam_types(db: Session = Depends(get_db)):
    exam_types = db.query(ExamTypeModel).all()
    return exam_types

@router.get("/types/{exam_type_id}", response_model=ExamType)
def get_exam_type(exam_type_id: int, db: Session = Depends(get_db)):
    exam_type = db.query(ExamTypeModel).filter(ExamTypeModel.id == exam_type_id).first()
    if not exam_type:
        raise HTTPException(status_code=404, detail="Exam type not found")
    return exam_type


@router.put("/types/{exam_type_id}", response_model=ExamType)
def update_exam_type(exam_type_id: int, exam_type_update: ExamTypeUpdate, db: Session = Depends(get_db)):
    exam_type = db.query(ExamTypeModel).filter(ExamTypeModel.id == exam_type_id).first()
    if not exam_type:
        raise HTTPException(status_code=404, detail="Exam type not found")
    
    update_data = exam_type_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(exam_type, field, value)
    
    db.commit()
    db.refresh(exam_type)
    return exam_type

@router.delete("/types/{exam_type_id}")
def delete_exam_type(exam_type_id: int, db: Session = Depends(get_db)):
    exam_type = db.query(ExamTypeModel).filter(ExamTypeModel.id == exam_type_id).first()
    if not exam_type:
        raise HTTPException(status_code=404, detail="Exam type not found")
    
    # Check if any exams are using this type
    exam_count = db.query(ExamModel).filter(ExamModel.exam_type_id == exam_type_id).count()
    if exam_count > 0:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot delete exam type. {exam_count} exam(s) are using this type."
        )
    
    db.delete(exam_type)
    db.commit()
    return {"message": "Exam type deleted successfully"}

# Exam endpoints
@router.post("/", response_model=Exam)
def create_exam(exam_in: ExamCreate, db: Session = Depends(get_db)):
    # Verify exam type exists
    exam_type = db.query(ExamTypeModel).filter(ExamTypeModel.id == exam_in.exam_type_id).first()
    if not exam_type:
        raise HTTPException(status_code=404, detail="Exam type not found")
    
    exam = ExamModel(**exam_in.dict())
    db.add(exam)
    db.commit()
    db.refresh(exam)
    return exam

@router.get("/", response_model=List[Exam])
def list_exams(db: Session = Depends(get_db)):
    exams = db.query(ExamModel).all()
    return exams

@router.get("/{exam_id}", response_model=Exam)
def get_exam(exam_id: int, db: Session = Depends(get_db)):
    exam = db.query(ExamModel).filter(ExamModel.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    return exam

@router.put("/{exam_id}", response_model=Exam)
def update_exam(exam_id: int, exam_update: ExamUpdate, db: Session = Depends(get_db)):
    exam = db.query(ExamModel).filter(ExamModel.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    
    # If exam_type_id is being updated, verify it exists
    if exam_update.exam_type_id is not None:
        exam_type = db.query(ExamTypeModel).filter(ExamTypeModel.id == exam_update.exam_type_id).first()
        if not exam_type:
            raise HTTPException(status_code=404, detail="Exam type not found")
    
    update_data = exam_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(exam, field, value)
    
    db.commit()
    db.refresh(exam)
    return exam

@router.delete("/{exam_id}")
def delete_exam(exam_id: int, db: Session = Depends(get_db)):
    exam = db.query(ExamModel).filter(ExamModel.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    
    # Check if any uploads are associated with this exam
    upload_count = db.query(UploadModel).filter(UploadModel.exam_id == exam_id).count()
    if upload_count > 0:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot delete exam. {upload_count} upload(s) are associated with this exam."
        )
    
    db.delete(exam)
    db.commit()
    return {"message": "Exam deleted successfully"}


@router.post("/uploads/pdf/", status_code=status.HTTP_202_ACCEPTED)
def upload_pdf(
    file: UploadFile = File(...),
    exam_id: int = Form(...),
    start_page: int = Form(1),
    end_page: int = Form(None),
    class_name: str = Form(None),
    subject_name: str = Form(None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """
    Accept a PDF or ZIP of PDFs, extract and queue background jobs for each file.
    Replicates the functionality from the Jupyter notebook for cloud processing.
    """
    logger.info(f"=== UPLOAD PDF STARTED ===")
    logger.info(f"Received file: {file.filename}")
    logger.info(f"File content type: {file.content_type}")
    logger.info(f"Exam ID: {exam_id}")
    logger.info(f"Page range: {start_page} to {end_page}")
    logger.info(f"Class name: {class_name}")
    logger.info(f"Subject name: {subject_name}")
    
    
    
    # Verify that the exam exists in the database
    exam = db.query(ExamModel).filter(ExamModel.id == exam_id).first()
    if not exam:
        logger.error(f"Exam with ID {exam_id} not found in database")
        raise HTTPException(
            status_code=404, 
            detail=f"Exam with ID {exam_id} not found. Please provide a valid exam ID."
        )
    
    upload_dir = "/tmp/scoresight_uploads"
    os.makedirs(upload_dir, exist_ok=True)
    logger.info(f"Upload directory: {upload_dir}")
    
    file_ext = os.path.splitext(file.filename)[-1].lower()
    logger.info(f"File extension: {file_ext}")
    saved_files = []
    
    try:
        if file_ext == ".zip":
            logger.info("Processing ZIP file...")
            zip_path = os.path.join(upload_dir, f"{uuid.uuid4()}.zip")
            logger.info(f"Saving ZIP to: {zip_path}")
            
            with open(zip_path, "wb") as f_out:
                shutil.copyfileobj(file.file, f_out)
            logger.info(f"ZIP file saved, size: {os.path.getsize(zip_path)} bytes")
            
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_contents = zip_ref.namelist()
                logger.info(f"ZIP contents: {zip_contents}")
                zip_ref.extractall(upload_dir)
                
            for name in zip_ref.namelist():
                if name.lower().endswith(".pdf"):
                    pdf_path = os.path.join(upload_dir, name)
                    saved_files.append(pdf_path)
                    logger.info(f"Extracted PDF: {pdf_path}")
                    
        elif file_ext == ".pdf":
            logger.info("Processing PDF file...")
            pdf_path = os.path.join(upload_dir, f"{uuid.uuid4()}.pdf")
            logger.info(f"Saving PDF to: {pdf_path}")
            
            with open(pdf_path, "wb") as f_out:
                shutil.copyfileobj(file.file, f_out)
            logger.info(f"PDF file saved, size: {os.path.getsize(pdf_path)} bytes")
            saved_files.append(pdf_path)
        else:
            logger.error(f"Unsupported file type: {file_ext}")
            raise HTTPException(status_code=400, detail="Only PDF or ZIP of PDFs supported.")
        
        logger.info(f"Total files to process: {len(saved_files)}")
        
        # Create upload records in database
        upload_records = []
        job_ids = []
        
        for idx, pdf_path in enumerate(saved_files):
            logger.info(f"=== PROCESSING FILE {idx + 1}/{len(saved_files)}: {pdf_path} ===")
            
            # Create upload record
            upload_record = UploadModel(
                exam_id=exam_id,
                filename=os.path.basename(pdf_path),
                start_page=start_page,
                end_page=end_page,
                status="queued"
            )
            logger.info(f"Creating upload record: {upload_record.filename}")
            
            db.add(upload_record)
            db.commit()
            db.refresh(upload_record)
            upload_records.append(upload_record)
            logger.info(f"Upload record created with ID: {upload_record.id}")
            
            # Prepare settings dictionary for Celery task
            settings_dict = settings.dict()
            logger.info(f"Settings dict prepared: {list(settings_dict.keys())}")
            logger.info(f"OpenAI API key present: {'OPENAI_API_KEY' in settings_dict and bool(settings_dict.get('OPENAI_API_KEY'))}")
            
            # Queue background Celery job with all parameters
            logger.info("=== QUEUEING CELERY TASK ===")
            logger.info(f"Task name: process_pdf_task")
            logger.info(f"PDF path: {pdf_path}")
            logger.info(f"Output dir: {upload_dir}")
            logger.info(f"Start page: {start_page}")
            logger.info(f"End page: {end_page}")
            logger.info(f"Class name: {class_name}")
            logger.info(f"Subject name: {subject_name}")
            
            try:
                job = process_pdf_task.delay(
                    pdf_path, 
                    upload_dir, 
                    settings_dict,
                    start_page=start_page,
                    end_page=end_page,
                    class_name=class_name,
                    subject_name=subject_name
                )
                logger.info(f"Celery task queued successfully!")
                logger.info(f"Job ID: {job.id}")
                logger.info(f"Job state: {job.state}")
                logger.info(f"Job status: {job.status}")
                
                job_ids.append(job.id)
                
                # Update upload record with job ID (you might want to add a job_id field to the model)
                upload_record.status = "queued"
                db.commit()
                logger.info(f"Upload record updated to queued status")
                
            except Exception as e:
                logger.error(f"Failed to queue Celery task: {str(e)}")
                logger.error(f"Exception type: {type(e)}")
                upload_record.status = "failed"
                db.commit()
                raise HTTPException(status_code=500, detail=f"Failed to queue processing job: {str(e)}")
        
        logger.info(f"=== UPLOAD COMPLETE ===")
        logger.info(f"Total job IDs: {job_ids}")
        logger.info(f"Total upload IDs: {[record.id for record in upload_records]}")
        
        return {
            "job_ids": job_ids, 
            "upload_ids": [record.id for record in upload_records],
            "status": "queued",
            "message": f"Processing {len(saved_files)} PDF(s) from page {start_page} to {end_page or 'end'}"
        }
        
    except Exception as e:
        logger.error(f"Error in upload_pdf: {str(e)}")
        logger.error(f"Exception type: {type(e)}")
        raise


async def process_pdf_upload(upload_id: int, file_location: str, db: Session):
    """Background task to process uploaded PDF file."""
    upload = db.query(UploadModel).filter(UploadModel.id == upload_id).first()
    if not upload:
        return

    try:
        # Update status to processing
        upload.status = "processing"
        db.commit()

        # Split PDF to pages
        pages = split_pdf_to_pages(file_location)

        # Prepare output directory
        output_dir = os.path.dirname(file_location)
        original_file_name = os.path.basename(file_location).replace('.pdf', '')

        # Process each page asynchronously
        results = []
        for idx, page_bytes in enumerate(pages):
            base64_image = encode_image_to_base64(page_bytes)
            # Save image for debugging
            save_image(base64_image, os.path.join(output_dir, 'page_pictures'), f'{original_file_name}_page{idx+1}.png')

            # Call OpenAI client with image and last known student name
            last_known_student_name = results[-1].get('studentName', '') if results else ''
            try:
                response = await OpenAIClient.ask_llm(base64_image, last_known_student_name)
                results.append(response)
            except Exception as e:
                print(f"OpenAI call failed for page {idx+1}: {e}")

        # Convert results to DataFrame
        df = pd.DataFrame()
        if results:
            # Flatten entries for each student
            rows = []
            for res in results:
                student_name = res.get('studentName', '')
                entries = res.get('entries', [])
                for entry in entries:
                    row = {
                        'Student Name': student_name,
                        'Question No': entry.get('questionNo', ''),
                        'Question': entry.get('question', ''),
                        'Answer': entry.get('answer', ''),
                        'Grading': entry.get('grading', ''),
                    }
                    rows.append(row)
            df = pd.DataFrame(rows)

        # Analyze results
        analysis_df = await analyze_misconceptions(df, OpenAIClient.api_key)

        # Save analysis report
        report_path = os.path.join(output_dir, f'report_{upload_id}.xlsx')
        analysis_df.to_excel(report_path, index=False)

        # Save report record
        report = ReportModel(
            exam_id=upload.exam_id,
            report_type="analysis",
            file_path=report_path
        )
        db.add(report)

        # Update upload status
        upload.status = "completed"
        db.commit()

    except Exception as e:
        upload.status = "failed"
        db.commit()
        print(f"Error processing upload {upload_id}: {e}")


@router.get("/jobs/{job_id}")
def get_job_status(job_id: str):
    """
    Get the status/result of a background job by Celery job ID.
    """
    logger.info(f"=== GET JOB STATUS ===")
    logger.info(f"Checking status for job ID: {job_id}")
    
    try:
        async_result = celery_app.AsyncResult(job_id)
        logger.info(f"AsyncResult created for job: {job_id}")
        
        # Get the current status
        status = async_result.status
        logger.info(f"Job status: {status}")
        logger.info(f"Job ready: {async_result.ready()}")
        logger.info(f"Job successful: {async_result.successful()}")
        logger.info(f"Job failed: {async_result.failed()}")
        
        # Prepare the response
        response = {
            "job_id": job_id,
            "status": status,
        }
        
        # Add result if the task is completed
        if async_result.ready():
            logger.info("Job is ready (completed)")
            if status == "SUCCESS":
                result = async_result.result
                logger.info(f"Job successful, result type: {type(result)}")
                logger.info(f"Job result keys: {result.keys() if isinstance(result, dict) else 'Not a dict'}")
                response["result"] = result
            elif status == "FAILURE":
                error_info = str(async_result.info)
                logger.error(f"Job failed with error: {error_info}")
                response["error"] = error_info
            else:
                result = async_result.result
                logger.info(f"Job status {status}, result: {result}")
                response["result"] = result
        else:
            logger.info("Job is not ready yet")
            response["result"] = None
            
        # Add progress info if available
        if hasattr(async_result, 'info') and async_result.info:
            logger.info(f"Job info available: {type(async_result.info)}")
            if isinstance(async_result.info, dict):
                logger.info(f"Job progress info: {async_result.info}")
                response["progress"] = async_result.info
                
        logger.info(f"Returning response: {response}")
        return response
        
    except Exception as e:
        logger.error(f"Error retrieving job status: {str(e)}")
        logger.error(f"Exception type: {type(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving job status: {str(e)}"
        )


@router.get("/jobs/")
def list_jobs():
    """
    List all active jobs and their statuses.
    """
    logger.info(f"=== LIST JOBS ===")
    
    try:
        # Get active tasks from Celery
        inspect = celery_app.control.inspect()
        logger.info(f"Celery inspect created: {inspect}")
        
        # Get active, scheduled, and reserved tasks
        active_tasks = inspect.active()
        scheduled_tasks = inspect.scheduled()
        reserved_tasks = inspect.reserved()
        
        logger.info(f"Active tasks response: {active_tasks}")
        logger.info(f"Scheduled tasks response: {scheduled_tasks}")
        logger.info(f"Reserved tasks response: {reserved_tasks}")
        
        jobs = []
        
        # Process active tasks
        if active_tasks:
            logger.info(f"Processing {len(active_tasks)} worker(s) with active tasks")
            for worker, tasks in active_tasks.items():
                logger.info(f"Worker {worker} has {len(tasks)} active tasks")
                for task in tasks:
                    job_info = {
                        "job_id": task["id"],
                        "name": task["name"],
                        "worker": worker,
                        "status": "ACTIVE",
                        "args": task.get("args", []),
                        "kwargs": task.get("kwargs", {})
                    }
                    jobs.append(job_info)
                    logger.info(f"Added active job: {job_info}")
        else:
            logger.info("No active tasks found")
        
        # Process scheduled tasks
        if scheduled_tasks:
            logger.info(f"Processing {len(scheduled_tasks)} worker(s) with scheduled tasks")
            for worker, tasks in scheduled_tasks.items():
                logger.info(f"Worker {worker} has {len(tasks)} scheduled tasks")
                for task in tasks:
                    job_info = {
                        "job_id": task["id"],
                        "name": task["name"],
                        "worker": worker,
                        "status": "SCHEDULED",
                        "eta": task.get("eta"),
                        "args": task.get("args", []),
                        "kwargs": task.get("kwargs", {})
                    }
                    jobs.append(job_info)
                    logger.info(f"Added scheduled job: {job_info}")
        else:
            logger.info("No scheduled tasks found")
        
        # Process reserved tasks
        if reserved_tasks:
            logger.info(f"Processing {len(reserved_tasks)} worker(s) with reserved tasks")
            for worker, tasks in reserved_tasks.items():
                logger.info(f"Worker {worker} has {len(tasks)} reserved tasks")
                for task in tasks:
                    job_info = {
                        "job_id": task["id"],
                        "name": task["name"],
                        "worker": worker,
                        "status": "RESERVED",
                        "args": task.get("args", []),
                        "kwargs": task.get("kwargs", {})
                    }
                    jobs.append(job_info)
                    logger.info(f"Added reserved job: {job_info}")
        else:
            logger.info("No reserved tasks found")
        
        result = {
            "jobs": jobs,
            "total": len(jobs)
        }
        
        logger.info(f"=== LIST JOBS COMPLETE ===")
        logger.info(f"Total jobs found: {len(jobs)}")
        return result
        
    except Exception as e:
        logger.error(f"Error retrieving jobs list: {str(e)}")
        logger.error(f"Exception type: {type(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving jobs list: {str(e)}"
        )


@router.get("/reports/{exam_id}")
def stream_exam_report(exam_id: int, db: Session = Depends(get_db)):
    """
    Stream the exam report as JSON lines for large analyses.
    """
    # Example: fetch report rows from DB or file, stream as JSON lines
    # Here, we simulate with a dummy generator
    def report_generator():
        # Replace with real DB/file streaming logic
        for i in range(100):
            yield f"{{\"row\": {i}}}\n"
            time.sleep(0.01)  # Simulate streaming delay
    return StreamingResponse(report_generator(), media_type="application/x-ndjson")


@router.get("/analysis/{exam_id}")
async def get_analysis(exam_id: int, db: Session = Depends(get_db)):
    """
    Get aggregated analysis for an exam including misconception analysis.
    """
    # Get exam
    exam = db.query(ExamModel).filter(ExamModel.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    
    # Get reports for this exam
    reports = db.query(ReportModel).filter(ReportModel.exam_id == exam_id).all()
    
    analysis_data = {
        "exam_id": exam_id,
        "exam_name": exam.name,
        "subject_name": exam.subject_name,
        "class_name": exam.class_name,
        "reports": [],
        "summary": {
            "total_reports": len(reports),
            "transcription_reports": 0,
            "analysis_reports": 0
        }
    }
    
    for report in reports:
        report_info = {
            "id": report.id,
            "type": report.report_type,
            "file_path": report.file_path,
            "created_at": report.created_at
        }
        analysis_data["reports"].append(report_info)
        
        if "transcription" in report.report_type:
            analysis_data["summary"]["transcription_reports"] += 1
        elif "analysis" in report.report_type:
            analysis_data["summary"]["analysis_reports"] += 1
    
    return analysis_data


@router.post("/analysis/generate/{exam_id}")
async def generate_analysis_from_transcription(
    exam_id: int,
    transcription_file_path: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings)
):
    """
    Generate analysis report from existing transcription data.
    """
    # Verify exam exists
    exam = db.query(ExamModel).filter(ExamModel.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    
    # Verify transcription file exists
    if not os.path.exists(transcription_file_path):
        raise HTTPException(status_code=404, detail="Transcription file not found")
    
    # Queue analysis generation job
    output_dir = os.path.dirname(transcription_file_path)
    job = generate_analysis_report.delay(transcription_file_path, output_dir, settings.dict())
    
    return {
        "job_id": job.id,
        "status": "queued",
        "message": f"Analysis generation queued for exam {exam_id}"
    }


@router.get("/download/transcription/{job_id}")
async def download_transcription_results(job_id: str):
    """
    Download transcription results (CSV format) for a completed job.
    """
    try:
        async_result = celery_app.AsyncResult(job_id)
        
        if not async_result.ready():
            raise HTTPException(status_code=202, detail="Job still processing")
        
        if async_result.status == "FAILURE":
            raise HTTPException(status_code=500, detail=f"Job failed: {async_result.info}")
        
        result = async_result.result
        transcription_file = result.get("transcription_file")
        
        if not transcription_file or not os.path.exists(transcription_file):
            raise HTTPException(status_code=404, detail="Transcription file not found")
        
        def file_generator():
            with open(transcription_file, "rb") as f:
                while chunk := f.read(8192):
                    yield chunk
        
        filename = os.path.basename(transcription_file)
        return StreamingResponse(
            file_generator(),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error downloading file: {str(e)}")


@router.get("/download/analysis/{job_id}")
async def download_analysis_results(job_id: str):
    """
    Download analysis results (Excel format) for a completed job.
    """
    try:
        async_result = celery_app.AsyncResult(job_id)
        
        if not async_result.ready():
            raise HTTPException(status_code=202, detail="Job still processing")
        
        if async_result.status == "FAILURE":
            raise HTTPException(status_code=500, detail=f"Job failed: {async_result.info}")
        
        result = async_result.result
        analysis_file = result.get("analysis_file")
        
        if not analysis_file or not os.path.exists(analysis_file):
            raise HTTPException(status_code=404, detail="Analysis file not found")
        
        def file_generator():
            with open(analysis_file, "rb") as f:
                while chunk := f.read(8192):
                    yield chunk
        
        filename = os.path.basename(analysis_file)
        return StreamingResponse(
            file_generator(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error downloading file: {str(e)}")


@router.get("/uploads/{upload_id}")
def get_upload_status(upload_id: int, db: Session = Depends(get_db)):
    """
    Get the status of a specific upload.
    """
    upload = db.query(UploadModel).filter(UploadModel.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")
    
    return {
        "upload_id": upload.id,
        "exam_id": upload.exam_id,
        "filename": upload.filename,
        "status": upload.status,
        "start_page": upload.start_page,
        "end_page": upload.end_page,
        "created_at": upload.created_at
    }


@router.delete("/jobs/{job_id}")
def cancel_job(job_id: str):
    """
    Cancel a running job by its ID.
    """
    try:
        celery_app.control.revoke(job_id, terminate=True)
        return {
            "job_id": job_id,
            "status": "cancelled",
            "message": f"Job {job_id} has been cancelled"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error cancelling job: {str(e)}"
        )


@router.get("/workers/")
def list_workers():
    """
    List all active Celery workers and their stats.
    """
    logger.info(f"=== LIST WORKERS ===")
    
    try:
        inspect = celery_app.control.inspect()
        logger.info(f"Celery inspect created: {inspect}")
        
        # Get worker stats
        stats = inspect.stats()
        active = inspect.active()
        registered = inspect.registered()
        
        logger.info(f"Worker stats response: {stats}")
        logger.info(f"Worker active tasks response: {active}")
        logger.info(f"Worker registered tasks response: {registered}")
        
        workers = []
        if stats:
            logger.info(f"Processing {len(stats)} worker(s)")
            for worker_name, worker_stats in stats.items():
                active_tasks_count = len(active.get(worker_name, [])) if active else 0
                registered_tasks_list = registered.get(worker_name, []) if registered else []
                
                worker_info = {
                    "name": worker_name,
                    "status": "online",
                    "pool": worker_stats.get("pool", {}),
                    "total_tasks": worker_stats.get("total", {}),
                    "active_tasks": active_tasks_count,
                    "registered_tasks": registered_tasks_list
                }
                workers.append(worker_info)
                logger.info(f"Worker {worker_name}: {active_tasks_count} active tasks, {len(registered_tasks_list)} registered tasks")
        else:
            logger.warning("No worker stats found - workers may not be running")
        
        result = {
            "workers": workers,
            "total_workers": len(workers)
        }
        
        logger.info(f"=== LIST WORKERS COMPLETE ===")
        logger.info(f"Total workers found: {len(workers)}")
        return result
        
    except Exception as e:
        logger.error(f"Error retrieving workers: {str(e)}")
        logger.error(f"Exception type: {type(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving workers: {str(e)}"
        )


@router.post("/analysis/topic/", status_code=status.HTTP_202_ACCEPTED)
async def analyze_topics(
    file: UploadFile = File(...),
    subject_name: str = "SST",
    settings: Settings = Depends(get_settings)
):
    """
    Accept a CSV file with questions, clean it, and queue a background job for topic categorization.
    """
    try:
        # Read the uploaded file into a DataFrame
        if file.filename.endswith('.csv'):
            df = pd.read_csv(file.file)
        elif file.filename.endswith(('.xls', '.xlsx')):
            df = pd.read_excel(file.file)
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type. Please upload a CSV or Excel file.")

        # Clean the question list to get unique questions
        cleaned_df = clean_question_list(df)
        
        # Convert the cleaned DataFrame to a list of dictionaries
        questions_data = cleaned_df.to_dict('records')

        # Queue the background task
        task = categorize_questions_task.delay(questions_data, subject_name, settings.dict())

        return {"job_id": task.id, "status": "queued", "message": "Topic analysis job started."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start topic analysis job: {str(e)}")
