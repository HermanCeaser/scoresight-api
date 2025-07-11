#!/usr/bin/env python3
"""
Simple API test client for testing the job status endpoints.
Run this after starting the FastAPI server to test the endpoints.
"""

import requests
import json
import time

BASE_URL = "http://localhost:8001/api/v1/exams"

def test_job_endpoints():
    """Test the job-related endpoints."""
    print("🧪 Testing Job Status API Endpoints...")
    
    # Test workers endpoint
    print("\n1. Testing workers endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/workers/")
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            workers = response.json()
            print(f"Workers: {json.dumps(workers, indent=2)}")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Error calling workers endpoint: {e}")
    
    # Test jobs list endpoint
    print("\n2. Testing jobs list endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/jobs/")
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            jobs = response.json()
            print(f"Jobs: {json.dumps(jobs, indent=2)}")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Error calling jobs list endpoint: {e}")
    
    # Test job status with a fake ID
    print("\n3. Testing job status endpoint with fake ID...")
    fake_job_id = "fake-job-123"
    try:
        response = requests.get(f"{BASE_URL}/jobs/{fake_job_id}")
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            status = response.json()
            print(f"Job Status: {json.dumps(status, indent=2)}")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Error calling job status endpoint: {e}")

def test_pdf_upload():
    """Test PDF upload to create a real job."""
    print("\n4. Testing PDF upload to create a real job...")
    
    # Create a dummy PDF file
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.pdf', delete=False) as f:
        f.write("%PDF-1.4\nDummy PDF content for testing")
        dummy_pdf_path = f.name
    
    try:
        with open(dummy_pdf_path, 'rb') as f:
            files = {'file': ('test.pdf', f, 'application/pdf')}
            response = requests.post(f"{BASE_URL}/uploads/pdf/", files=files)
            
        print(f"Upload Status: {response.status_code}")
        if response.status_code == 202:
            result = response.json()
            print(f"Upload Result: {json.dumps(result, indent=2)}")
            
            # Test job status for real job IDs
            job_ids = result.get('job_ids', [])
            for job_id in job_ids:
                print(f"\n5. Testing job status for real job: {job_id}")
                for i in range(5):  # Check status 5 times
                    try:
                        response = requests.get(f"{BASE_URL}/jobs/{job_id}")
                        if response.status_code == 200:
                            status = response.json()
                            print(f"Attempt {i+1} - Status: {status['status']}")
                            if status.get('progress'):
                                print(f"Progress: {status['progress']}")
                            if status['status'] in ['SUCCESS', 'FAILURE']:
                                print(f"Final result: {status.get('result', status.get('error'))}")
                                break
                        time.sleep(1)
                    except Exception as e:
                        print(f"Error checking job status: {e}")
        else:
            print(f"Upload Error: {response.text}")
            
    except Exception as e:
        print(f"Error testing PDF upload: {e}")
    finally:
        # Cleanup
        import os
        try:
            os.unlink(dummy_pdf_path)
        except:
            pass

if __name__ == "__main__":
    print("🚀 Starting API tests...")
    print("Make sure FastAPI server is running on http://localhost:8001")
    print("and Celery worker is running!")
    
    test_job_endpoints()
    
    # Ask user if they want to test PDF upload (creates real jobs)
    test_upload = input("\nDo you want to test PDF upload (creates real jobs)? [y/N]: ")
    if test_upload.lower() in ['y', 'yes']:
        test_pdf_upload()
    
    print("\n✅ API tests completed!")
