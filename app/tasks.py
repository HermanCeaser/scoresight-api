import math
from .celery_app import celery_app
from .core.pdf_utils import split_pdf_to_pages, encode_image_to_base64, save_page_image, get_pdf_page_count
from .core.analysis import analyze_misconceptions_sync, clean_transcribed_data, clean_question_list
from .core.openai_client import OpenAIClient
from .deps import Settings
import pandas as pd
import os
import tempfile
import json
import asyncio
import logging
from typing import Dict, Any, List

# Configure logging for this module
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

@celery_app.task(bind=True, name="process_pdf_task")
def process_pdf_task(self, pdf_path: str, output_dir: str, settings_dict: dict, start_page: int = 1, end_page: int = None, class_name: str = None, subject_name: str = None):
    """
    Celery task to process a PDF, split to pages, run LLM extraction, and generate analysis reports.
    This replicates the functionality from the Jupyter notebook.
    """
    logger.info(f"=== CELERY TASK STARTED ===")
    logger.info(f"Task ID: {self.request.id}")
    logger.info(f"PDF path: {pdf_path}")
    logger.info(f"Output dir: {output_dir}")
    logger.info(f"Start page: {start_page}")
    logger.info(f"End page: {end_page}")
    logger.info(f"Class name: {class_name}")
    logger.info(f"Subject name: {subject_name}")
    logger.info(f"Settings dict keys: {list(settings_dict.keys())}")
    
    try:
        # Update task state to indicate processing has started
        logger.info("Updating task state to PROCESSING...")
        self.update_state(state='PROCESSING', meta={'current': 0, 'total': 0, 'status': 'Starting PDF processing...'})
        
        # Check if PDF file exists
        if not os.path.exists(pdf_path):
            logger.error(f"PDF file does not exist: {pdf_path}")
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        logger.info(f"PDF file exists, size: {os.path.getsize(pdf_path)} bytes")
        
        # Initialize settings and OpenAI client
        logger.info("Initializing settings and OpenAI client...")
        settings = Settings(**settings_dict)
        logger.info(f"Settings initialized successfully")
        logger.info(f"OpenAI API key present: {bool(settings.OPENAI_API_KEY)}")
        logger.info(f"OpenAI model: {settings.OPENAI_MODEL}")
        
        openai_client = OpenAIClient(settings.OPENAI_API_KEY, model=settings.OPENAI_MODEL)
        logger.info(f"OpenAI client initialized successfully")
        logger.info(f"API key starts with: {settings.OPENAI_API_KEY[:10]}...")
        logger.info(f"API key ends with: ...{settings.OPENAI_API_KEY[-10:]}")
        
        # Get total page count first
        logger.info("Getting PDF page count...")
        total_pdf_pages = get_pdf_page_count(pdf_path)
        logger.info(f"Total PDF pages: {total_pdf_pages}")
        
        # Set end_page if not provided
        if end_page is None:
            end_page = total_pdf_pages
            logger.info(f"End page set to total pages: {end_page}")
        
        # Validate page range
        if start_page < 1:
            start_page = 1
            logger.info(f"Start page adjusted to: {start_page}")
        if end_page > total_pdf_pages:
            end_page = total_pdf_pages
            logger.info(f"End page adjusted to: {end_page}")
        
        logger.info(f"Final page range: {start_page} to {end_page}")
        
        self.update_state(state='PROCESSING', meta={'current': 0, 'total': 0, 'status': f'Splitting PDF (pages {start_page}-{end_page})...'})
        
        # Split PDF to pages with specified range
        logger.info("Starting PDF page splitting...")
        page_images = split_pdf_to_pages(pdf_path, start_page, end_page)
        total_pages = len(page_images)
        logger.info(f"PDF split complete. Total pages extracted: {total_pages}")
        
        if total_pages == 0:
            logger.error("No pages were extracted from the PDF")
            raise ValueError("No pages could be extracted from the PDF")
        
        self.update_state(state='PROCESSING', meta={'current': 0, 'total': total_pages, 'status': f'Processing {total_pages} pages...'})
        
        # Process each page with OpenAI
        all_results = []
        current_student_name = ""  # Track student name across pages
        
        logger.info(f"Starting page-by-page processing...")
        
        for idx, img_bytes in enumerate(page_images):
            # Update progress
            current_page = idx + 1
            actual_page_number = start_page + idx
            
            logger.info(f"=== PROCESSING PAGE {current_page}/{total_pages} (PDF page {actual_page_number}) ===")
            
            self.update_state(
                state='PROCESSING', 
                meta={
                    'current': current_page, 
                    'total': total_pages, 
                    'status': f'Analyzing page {actual_page_number} ({current_page} of {total_pages})...'
                }
            )
            
            # Convert to base64
            logger.info("Converting image to base64...")
            base64_img = encode_image_to_base64(img_bytes)
            logger.info(f"Base64 conversion complete, length: {len(base64_img)}")
            
            # Save image for debugging
            original_filename = os.path.basename(pdf_path).replace('.pdf', '')
            logger.info(f"Saving page image for debugging...")
            save_page_image(base64_img, original_filename, actual_page_number, output_dir)
            logger.info(f"Page image saved")
            
            # Call OpenAI for transcription and analysis
            try:
                logger.info(f"Calling OpenAI API for page {actual_page_number}...")
                logger.info(f"Current student name: '{current_student_name}'")
                
                # Use async OpenAI call from notebook workflow
                result = asyncio.run(openai_client.ask_exam_page_image(base64_img, current_student_name))
                logger.info(f"OpenAI API call successful")
                logger.info(f"Result type: {type(result)}")
                logger.info(f"Result: {json.dumps(result, indent=2) if isinstance(result, dict) else str(result)}")
                
                if result and 'studentName' in result:
                    if result['studentName']:
                        current_student_name = result['studentName']
                        logger.info(f"Updated student name: '{current_student_name}'")
                    
                    # Add page number to each entry for tracking
                    entries = result.get('entries', [])
                    logger.info(f"Found {len(entries)} entries on page {actual_page_number}")
                    
                    for entry in entries:
                        entry['scanPageNo'] = actual_page_number
                        entry['studentName'] = current_student_name
                        entry['className'] = class_name or "Unknown"
                        entry['subjectName'] = subject_name or "Unknown"
                    
                    all_results.append(result)
                    logger.info(f"Page {actual_page_number} processed successfully")
                else:
                    logger.warning(f"No valid result from OpenAI for page {actual_page_number}")
                    
            except Exception as e:
                logger.error(f"OpenAI call failed for page {actual_page_number}: {str(e)}")
                logger.error(f"Exception type: {type(e)}")
                # Continue with next page
                continue
        
        logger.info(f"All pages processed. Total results: {len(all_results)}")
        
        # Convert results to DataFrame for analysis (replicating notebook logic)
        self.update_state(state='PROCESSING', meta={'current': total_pages, 'total': total_pages, 'status': 'Converting results to tabular format...'})
        
        logger.info("Converting results to DataFrame...")
        all_entries = []
        for result_idx, result in enumerate(all_results):
            student_name = result.get('studentName', current_student_name)
            entries = result.get('entries', [])
            logger.info(f"Result {result_idx + 1}: Student '{student_name}', {len(entries)} entries")
            
            for entry in entries:
                row = {
                    'Student Name': student_name,
                    'Question No': entry.get('questionNo', ''),
                    'Question': entry.get('question', ''),
                    'Answer': entry.get('answer', ''),
                    'Grading': entry.get('grading', ''),
                    'ScanPageNo': entry.get('scanPageNo', 0),
                    'ClassName': entry.get('className', class_name or 'Unknown'),
                    'SubjectName': entry.get('subjectName', subject_name or 'Unknown')
                }
                all_entries.append(row)
        
        logger.info(f"Total entries created: {len(all_entries)}")
        
        if not all_entries:
            logger.error("No exam entries were extracted from the PDF")
            raise ValueError("No exam entries were extracted from the PDF")
        
        df = pd.DataFrame(all_entries)
        logger.info(f"DataFrame created with shape: {df.shape}")
        
        # Clean the transcribed data
        self.update_state(state='PROCESSING', meta={'current': total_pages, 'total': total_pages, 'status': 'Cleaning and standardizing data...'})
        
        logger.info("Cleaning transcribed data...")
        df = clean_transcribed_data(df)
        logger.info(f"Data cleaned, final DataFrame shape: {df.shape}")
        
        # Save raw transcription data
        original_filename = os.path.basename(pdf_path).replace('.pdf', '')
        csv_path = os.path.join(output_dir, f"{original_filename}_transcription.csv")
        logger.info(f"Saving transcription data to: {csv_path}")
        df.to_csv(csv_path, index=False)
        logger.info(f"Transcription data saved successfully")
        
        # Generate analysis report (replicating notebook analysis logic)
        self.update_state(state='PROCESSING', meta={'current': total_pages, 'total': total_pages, 'status': 'Analyzing misconceptions...'})
        
        analysis_path = None
        try:
            logger.info("Starting misconception analysis...")
            analysis_df = analyze_misconceptions_sync(df, settings.OPENAI_API_KEY)
            logger.info(f"Analysis complete, result shape: {analysis_df.shape}")
            
            # Save analysis report
            analysis_path = os.path.join(output_dir, f"{original_filename}_analysis.xlsx")
            logger.info(f"Saving analysis report to: {analysis_path}")
            
            with pd.ExcelWriter(analysis_path) as writer:
                analysis_df.to_excel(writer, index=False, sheet_name="Question_Analysis")
                df.to_excel(writer, index=False, sheet_name="Raw_Transcription")
            
            logger.info(f"Analysis report saved successfully")
            
        except Exception as e:
            logger.error(f"Analysis generation failed: {str(e)}")
            logger.error(f"Exception type: {type(e)}")
            analysis_path = None
        
        # Prepare final result
        result_summary = {
            "status": "completed", 
            "transcription_file": csv_path,
            "analysis_file": analysis_path,
            "pages_processed": total_pages,
            "start_page": start_page,
            "end_page": start_page + total_pages - 1,
            "total_entries": len(all_entries),
            "students_found": df['Student Name'].nunique() if len(df) > 0 else 0,
            "summary": {
                "total_questions": len(df.groupby('Question No')) if len(df) > 0 else 0,
                "total_answers": len(df[df['Answer'].str.strip() != '']) if len(df) > 0 else 0,
                "graded_answers": len(df[df['Grading'].isin(['Correct', 'Incorrect'])]) if len(df) > 0 else 0
            }
        }

        # Trigger topic categorization task
        if csv_path and subject_name:
            logger.info(f"Triggering topic categorization for subject: {subject_name}")
            try:
                cleaned_df = clean_question_list(df.copy())
                questions_data = cleaned_df.to_dict('records')
                
                if questions_data:
                    categorize_job = categorize_questions_task.delay(
                        questions_data,
                        subject_name,
                        settings_dict
                    )
                    logger.info(f"Topic categorization task queued with ID: {categorize_job.id}")
                    result_summary['topic_analysis_job_id'] = categorize_job.id
                else:
                    logger.warning("No unique questions found to categorize.")

            except Exception as e:
                logger.error(f"Failed to queue topic categorization task: {str(e)}")
        
        logger.info(f"=== CELERY TASK COMPLETED SUCCESSFULLY ===")
        logger.info(f"Final result: {result_summary}")
        
        return result_summary
        
    except Exception as exc:
        # Update task state to indicate failure
        error_msg = str(exc)
        logger.error(f"=== CELERY TASK FAILED ===")
        logger.error(f"Error: {error_msg}")
        logger.error(f"Exception type: {type(exc)}")
        
        self.update_state(
            state='FAILURE',
            meta={
                'error': error_msg,
                'status': f'Processing failed: {error_msg}'
            }
        )
        raise exc


@celery_app.task(bind=True, name="generate_analysis_report")
def generate_analysis_report(self, transcription_file_path: str, output_dir: str, settings_dict: dict):
    """
    Generate analysis report from existing transcription data.
    """
    try:
        self.update_state(state='PROCESSING', meta={'status': 'Loading transcription data...'})
        
        settings = Settings(**settings_dict)
        
        # Load data
        df = pd.read_csv(transcription_file_path)
        df = clean_transcribed_data(df)
        
        self.update_state(state='PROCESSING', meta={'status': 'Analyzing misconceptions...'})
        
        # Generate analysis
        analysis_df = analyze_misconceptions_sync(df, settings.OPENAI_API_KEY)
        
        # Save report
        base_name = os.path.basename(transcription_file_path).replace('_transcription.csv', '')
        analysis_path = os.path.join(output_dir, f"{base_name}_analysis.xlsx")
        
        with pd.ExcelWriter(analysis_path) as writer:
            analysis_df.to_excel(writer, index=False, sheet_name="Question_Analysis")
            df.to_excel(writer, index=False, sheet_name="Raw_Transcription")
        
        return {
            "status": "completed",
            "analysis_file": analysis_path,
            "summary": {
                "questions_analyzed": len(analysis_df),
                "total_entries": len(df)
            }
        }
        
    except Exception as exc:
        self.update_state(
            state='FAILURE',
            meta={
                'error': str(exc),
                'status': f'Analysis generation failed: {str(exc)}'
            }
        )
        raise exc


@celery_app.task(bind=True, name="categorize_questions_task")
def categorize_questions_task(self, questions_data: List[Dict], subject_name: str, settings_dict: dict):
    """
    Celery task to categorize questions by topic using OpenAI.
    """
    logger.info(f"=== TOPIC CATEGORIZATION TASK STARTED ===: {self.request.id}")
    logger.info(f"Processing {len(questions_data)} questions for subject: {subject_name}")
    if questions_data:
        logger.debug(f"Sample of questions_data: {json.dumps(questions_data[:2], indent=2)}")

    try:
        self.update_state(state='PROCESSING', meta={'current': 0, 'total': len(questions_data), 'status': 'Starting topic categorization...'})
        
        settings = Settings(**settings_dict)
        openai_client = OpenAIClient(settings.OPENAI_API_KEY, model=settings.OPENAI_MODEL)

        subject_topics = {
            "SST": [
                "Physical and Human Geography", "Civics and Governance", "History and Heritage",
                "Economic Activities and Development", "Social Systems and Practices", "Environmental Conservation and Management",
            ],
            "Mathematics": [
                "Numbers and Numeration", "Basic Operations", "Fractions and Decimals",
                "Measurement", "Geometry and Shapes", "Money and Consumer Math",
                "Statistics and Data Handling", "Algebra and Patterns"
            ],
            "Science": [
                "Living Things and Life Processes", "Human Body Systems", "Plants and Animals",
                "Materials and Their Properties", "Energy and Forces", "Earth and Space",
                "Environmental Science", "Health and Safety"
            ],
            "English": [
                "Reading Comprehension", "Grammar and Language Structure", "Vocabulary Development",
                "Writing Skills", "Speaking and Listening", "Literature Appreciation",
                "Spelling and Punctuation", "Creative Writing"
            ],
            "CRE": [
                "Biblical Stories and Characters", "Christian Values and Morals", "Prayer and Worship",
                "Church History", "Religious Ceremonies and Celebrations", "Christian Living",
                "Biblical Geography", "Faith and Beliefs"
            ]
        }

        topics = subject_topics.get(subject_name, [])
        if not topics:
            logger.warning(f"No topics found for subject: {subject_name}")
            return {"status": "FAILED", "error": f"Topic classification not available for subject: {subject_name}"}

        chunk_size = 30
        total_questions = len(questions_data)
        total_batches = math.ceil(total_questions / chunk_size)
        all_results = []

        logger.info(f"Starting to process {total_questions} questions in {total_batches} batches.")
        for i in range(0, total_questions, chunk_size):
            batch_num = i//chunk_size + 1
            chunk = questions_data[i:i+chunk_size]
            logger.info(f"Processing batch {batch_num}/{total_batches} with {len(chunk)} questions.")
            self.update_state(state='PROCESSING', meta={'current': i, 'total': total_questions, 'status': f'Processing batch {batch_num}/{total_batches}'})
            
            try:
                logger.debug(f"Sending chunk to OpenAI: {json.dumps(chunk, indent=2)}")
                results = asyncio.run(openai_client.get_question_topics(chunk, subject_name, topics))
                logger.info(f"Received {len(results)} results for batch {batch_num}.")
                logger.debug(f"Results from OpenAI: {json.dumps(results, indent=2)}")
                all_results.extend(results)
            except Exception as e:
                logger.error(f"Error processing batch {batch_num}: {str(e)}", exc_info=True)
                # Optionally, decide if you want to continue or fail the whole task
                continue

        logger.info(f"Finished processing all batches. Total results: {len(all_results)}")

        # Create a DataFrame from the results
        result_df = pd.DataFrame(questions_data)
        topic_df = pd.DataFrame(all_results)
        
        # Merge the results based on question number
        logger.info("Merging original questions with topic analysis results.")
        merged_df = pd.merge(result_df, topic_df, left_on="Question No", right_on="question_no", how="left")
        merged_df.drop(columns=["question_no"], inplace=True, errors='ignore')
        logger.debug(f"Merged DataFrame shape: {merged_df.shape}")
        
        # Save the results to a CSV file
        output_dir = "/tmp/scoresight_reports"
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"{subject_name}_topic_analysis_{self.request.id}.csv")
        logger.info(f"Saving topic analysis results to: {output_path}")
        merged_df.to_csv(output_path, index=False)

        final_result = {"status": "completed", "output_file": output_path, "questions_processed": len(merged_df)}
        logger.info(f"=== TOPIC CATEGORIZATION TASK COMPLETED SUCCESSFULLY ===")
        logger.info(f"Final result: {final_result}")
        return final_result

    except Exception as exc:
        logger.error(f"=== TOPIC CATEGORIZATION TASK FAILED ===: {self.request.id}", exc_info=True)
        self.update_state(state='FAILURE', meta={'error': str(exc), 'status': 'Processing failed'})
        raise exc
