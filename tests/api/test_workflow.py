#!/usr/bin/env python3
"""
Test script to validate the complete ScoreSight API workflow.
This script demonstrates the full PDF processing pipeline.
"""

import requests
import time
import json
import os
from pathlib import Path

# Configuration
API_BASE_URL = "http://localhost:8001"
TEST_PDF_PATH = "test_exam.pdf"  # You would need to provide a test PDF

def test_complete_workflow():
    """Test the complete API workflow."""
    
    print("🚀 Testing ScoreSight API Complete Workflow")
    print("=" * 50)
    
    # 1. Health check
    print("1. Testing API health...")
    try:
        response = requests.get(f"{API_BASE_URL}/health")
        if response.status_code == 200:
            print("✅ API is healthy")
        else:
            print("❌ API health check failed")
            return
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to API. Make sure the server is running on port 8000")
        return
    
    # 2. Create exam type
    print("\n2. Creating exam type...")
    exam_type_data = {
        "name": "MIDTERM",
        "description": "Test midterm examination"
    }
    response = requests.post(f"{API_BASE_URL}/api/v1/exams/types/", json=exam_type_data)
    if response.status_code == 200:
        exam_type_id = response.json()["id"]
        print(f"✅ Exam type created with ID: {exam_type_id}")
    else:
        print(f"⚠️  Exam type creation returned: {response.status_code}")
        # Try to use existing exam type
        response = requests.get(f"{API_BASE_URL}/api/v1/exams/types/")
        if response.json():
            exam_type_id = response.json()[0]["id"]
        else:
            exam_type_id = 1
    
    # 3. Create exam
    print("\n3. Creating exam...")
    exam_data = {
        "title": "Test Mathematics Exam",
        "subject": "Mathematics",
        "class_name": "Grade 10A",
        "exam_type_id": exam_type_id
    }
    response = requests.post(f"{API_BASE_URL}/api/v1/exams/", json=exam_data)
    if response.status_code == 200:
        exam_id = response.json()["id"]
        print(f"✅ Exam created with ID: {exam_id}")
    else:
        print(f"❌ Exam creation failed: {response.status_code}")
        return
    
    # 4. Test PDF upload (if test file exists)
    if os.path.exists(TEST_PDF_PATH):
        print(f"\n4. Uploading PDF: {TEST_PDF_PATH}")
        with open(TEST_PDF_PATH, 'rb') as f:
            files = {'file': f}
            data = {
                'exam_id': exam_id,
                'start_page': 1,
                'end_page': 3,  # Process only first 3 pages for testing
                'class_name': 'Grade 10A',
                'subject_name': 'Mathematics'
            }
            response = requests.post(
                f"{API_BASE_URL}/api/v1/exams/uploads/pdf/", 
                files=files, 
                data=data
            )
        
        if response.status_code == 202:
            result = response.json()
            job_id = result["job_ids"][0]
            print(f"✅ PDF uploaded successfully. Job ID: {job_id}")
            
            # 5. Monitor job progress
            print("\n5. Monitoring job progress...")
            while True:
                response = requests.get(f"{API_BASE_URL}/api/v1/exams/jobs/{job_id}")
                if response.status_code == 200:
                    job_status = response.json()
                    status = job_status["status"]
                    print(f"   Status: {status}")
                    
                    if "progress" in job_status and job_status["progress"]:
                        progress = job_status["progress"]
                        if "current" in progress and "total" in progress:
                            print(f"   Progress: {progress['current']}/{progress['total']}")
                        if "status" in progress:
                            print(f"   Details: {progress['status']}")
                    
                    if status in ["SUCCESS", "FAILURE"]:
                        break
                    
                    time.sleep(5)  # Wait 5 seconds before checking again
                else:
                    print(f"❌ Error checking job status: {response.status_code}")
                    break
            
            # 6. Download results if successful
            if status == "SUCCESS":
                print("\n6. Downloading results...")
                
                # Download transcription
                response = requests.get(f"{API_BASE_URL}/api/v1/exams/download/transcription/{job_id}")
                if response.status_code == 200:
                    with open(f"transcription_{job_id}.csv", "wb") as f:
                        f.write(response.content)
                    print("✅ Transcription CSV downloaded")
                
                # Download analysis
                response = requests.get(f"{API_BASE_URL}/api/v1/exams/download/analysis/{job_id}")
                if response.status_code == 200:
                    with open(f"analysis_{job_id}.xlsx", "wb") as f:
                        f.write(response.content)
                    print("✅ Analysis Excel downloaded")
                
                print(f"\n🎉 Complete workflow test successful!")
                print(f"   Job ID: {job_id}")
                print(f"   Transcription file: transcription_{job_id}.csv")
                print(f"   Analysis file: analysis_{job_id}.xlsx")
            else:
                print(f"❌ Job failed with status: {status}")
        else:
            print(f"❌ PDF upload failed: {response.status_code}")
            print(f"Response: {response.text}")
    else:
        print(f"\n4. Skipping PDF upload test (no test file: {TEST_PDF_PATH})")
        print("   To test PDF processing, place a test PDF file at:", TEST_PDF_PATH)
    
    # 7. Test other endpoints
    print(f"\n7. Testing other endpoints...")
    
    # List jobs
    response = requests.get(f"{API_BASE_URL}/api/v1/exams/jobs/")
    if response.status_code == 200:
        jobs = response.json()
        print(f"✅ Jobs endpoint working. Total jobs: {jobs['total']}")
    
    # List workers
    response = requests.get(f"{API_BASE_URL}/api/v1/exams/workers/")
    if response.status_code == 200:
        workers = response.json()
        print(f"✅ Workers endpoint working. Total workers: {workers['total_workers']}")
    
    # Get exam analysis
    response = requests.get(f"{API_BASE_URL}/api/v1/exams/analysis/{exam_id}")
    if response.status_code == 200:
        print("✅ Analysis endpoint working")
    
    print(f"\n✨ API workflow test completed!")

if __name__ == "__main__":
    test_complete_workflow()
