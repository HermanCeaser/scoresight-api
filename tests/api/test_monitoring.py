#!/usr/bin/env python3
"""
Test script to validate Celery + Flower setup.
"""
import sys
import time
import requests
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_flower_api():
    """Test Flower monitoring API."""
    try:
        # Test if Flower is accessible
        response = requests.get("http://localhost:5555/api/workers", timeout=5)
        if response.status_code == 200:
            workers = response.json()
            print(f"✅ Flower is accessible")
            print(f"✅ Found {len(workers)} workers")
            for worker_name, worker_info in workers.items():
                print(f"   Worker: {worker_name}")
                print(f"   Status: {worker_info.get('status', 'unknown')}")
            return True
        else:
            print(f"❌ Flower returned status {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Cannot connect to Flower: {e}")
        return False

def test_task_monitoring():
    """Test sending a task and monitoring it via Flower."""
    try:
        from app.tasks import process_pdf_task
        
        print("📤 Sending test task...")
        result = process_pdf_task.delay(
            "/tmp/test.pdf", 
            "/tmp", 
            {"OPENAI_API_KEY": "test"}, 
            1, 1, "test", "test"
        )
        
        print(f"✅ Task sent: {result.id}")
        
        # Wait a moment for task to appear in Flower
        time.sleep(2)
        
        # Check task in Flower
        response = requests.get(f"http://localhost:5555/api/task/info/{result.id}", timeout=5)
        if response.status_code == 200:
            task_info = response.json()
            print(f"✅ Task visible in Flower")
            print(f"   State: {task_info.get('state', 'unknown')}")
            print(f"   Worker: {task_info.get('worker', 'unknown')}")
        else:
            print(f"⚠️  Task not yet visible in Flower (status: {response.status_code})")
        
        # Cancel the task
        result.revoke(terminate=True)
        print(f"🚫 Task cancelled")
        
        return True
        
    except Exception as e:
        print(f"❌ Task monitoring test failed: {e}")
        return False

if __name__ == '__main__':
    print("🧪 Testing Celery + Flower Setup")
    print("=" * 40)
    
    print("\n1. Testing Flower accessibility...")
    flower_ok = test_flower_api()
    
    if flower_ok:
        print("\n2. Testing task monitoring...")
        task_ok = test_task_monitoring()
    else:
        print("\n⚠️  Skipping task test - Flower not accessible")
        task_ok = False
    
    print("\n" + "=" * 40)
    if flower_ok and task_ok:
        print("🎉 All tests passed! Your setup is ready.")
    else:
        print("❌ Some tests failed. Check the output above.")
        if not flower_ok:
            print("💡 Make sure to start Flower: make celery-monitor")
