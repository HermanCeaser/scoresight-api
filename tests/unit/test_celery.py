#!/usr/bin/env python3
"""
Test script to diagnose Celery connectivity issues.
"""
import os
import sys
import logging
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.celery_app import celery_app
from app.deps import get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_celery_connectivity():
    """Test Celery broker connectivity and worker availability."""
    
    logger.info("=== CELERY CONNECTIVITY TEST ===")
    
    # Check settings
    settings = get_settings()
    logger.info(f"Broker URL: {settings.CELERY_BROKER_URL}")
    logger.info(f"Result Backend: {settings.CELERY_RESULT_BACKEND}")
    
    # Test 1: Basic Celery app info
    logger.info(f"Celery app: {celery_app}")
    logger.info(f"Celery main: {celery_app.main}")
    logger.info(f"Registered tasks: {list(celery_app.tasks.keys())}")
    
    # Test 2: Try to get worker stats
    try:
        logger.info("=== Testing worker connectivity ===")
        inspect = celery_app.control.inspect()
        stats = inspect.stats()
        logger.info(f"Worker stats: {stats}")
        
        if stats:
            logger.info(f"✅ Found {len(stats)} workers")
            for worker_name, worker_stats in stats.items():
                logger.info(f"Worker: {worker_name}")
                logger.info(f"  Pool: {worker_stats.get('pool', {})}")
                logger.info(f"  Total tasks: {worker_stats.get('total', {})}")
        else:
            logger.warning("❌ No workers found")
            
    except Exception as e:
        logger.error(f"❌ Worker connectivity failed: {e}")
    
    # Test 3: Try to ping workers
    try:
        logger.info("=== Pinging workers ===")
        ping_result = inspect.ping()
        logger.info(f"Ping result: {ping_result}")
        
        if ping_result:
            logger.info(f"✅ {len(ping_result)} workers responded to ping")
        else:
            logger.warning("❌ No workers responded to ping")
            
    except Exception as e:
        logger.error(f"❌ Ping failed: {e}")
    
    # Test 4: Check registered tasks
    try:
        logger.info("=== Checking registered tasks ===")
        registered = inspect.registered()
        logger.info(f"Registered tasks: {registered}")
        
        if registered:
            for worker, tasks in registered.items():
                logger.info(f"Worker {worker} has tasks: {tasks}")
                if 'process_pdf_task' in tasks:
                    logger.info(f"✅ process_pdf_task is registered on {worker}")
                else:
                    logger.warning(f"❌ process_pdf_task NOT registered on {worker}")
                    
                if 'app.tasks.process_pdf_task' in tasks:
                    logger.info(f"✅ app.tasks.process_pdf_task is registered on {worker}")
                else:
                    logger.warning(f"❌ app.tasks.process_pdf_task NOT registered on {worker}")
        else:
            logger.warning("❌ No registered tasks found")
            
    except Exception as e:
        logger.error(f"❌ Failed to check registered tasks: {e}")
    
    # Test 5: Try to send a simple task
    try:
        logger.info("=== Testing task sending ===")
        
        # Try to send built-in celery.ping task first
        try:
            result = celery_app.send_task('celery.ping')
            logger.info(f"✅ Built-in ping task sent: {result.id}")
        except Exception as e:
            logger.error(f"❌ Failed to send built-in ping task: {e}")
        
        # Try to send our custom task
        try:
            result = celery_app.send_task('process_pdf_task', 
                                        args=['/tmp/test.pdf', '/tmp', {}, 1, 1, 'test', 'test'])
            logger.info(f"✅ Custom task sent with 'process_pdf_task': {result.id}")
            logger.info(f"Task state: {result.state}")
            
            # Cancel it immediately
            celery_app.control.revoke(result.id, terminate=True)
            logger.info(f"Task cancelled")
            
        except Exception as e:
            logger.error(f"❌ Failed to send custom task with 'process_pdf_task': {e}")
            
        # Try with full module path
        try:
            result = celery_app.send_task('app.tasks.process_pdf_task', 
                                        args=['/tmp/test.pdf', '/tmp', {}, 1, 1, 'test', 'test'])
            logger.info(f"✅ Custom task sent with full path: {result.id}")
            logger.info(f"Task state: {result.state}")
            
            # Cancel it immediately
            celery_app.control.revoke(result.id, terminate=True)
            logger.info(f"Task cancelled")
            
        except Exception as e:
            logger.error(f"❌ Failed to send custom task with full path: {e}")
            
    except Exception as e:
        logger.error(f"❌ Task sending test failed: {e}")

def test_broker_connection():
    """Test direct broker connection."""
    
    logger.info("=== BROKER CONNECTION TEST ===")
    
    settings = get_settings()
    broker_url = settings.CELERY_BROKER_URL
    
    if broker_url.startswith('redis://'):
        try:
            import redis
            # Parse Redis URL
            if '://' in broker_url:
                url_parts = broker_url.split('://')[1]  # Remove redis://
                if '@' in url_parts:
                    # redis://user:pass@host:port/db
                    auth_host = url_parts.split('@')
                    host_port_db = auth_host[1]
                else:
                    # redis://host:port/db
                    host_port_db = url_parts
                    
                parts = host_port_db.split('/')
                host_port = parts[0]
                db = int(parts[1]) if len(parts) > 1 else 0
                
                if ':' in host_port:
                    host, port = host_port.split(':')
                    port = int(port)
                else:
                    host = host_port
                    port = 6379
                    
                logger.info(f"Testing Redis connection to {host}:{port} db={db}")
                
                r = redis.Redis(host=host, port=port, db=db)
                r.ping()
                logger.info("✅ Redis connection successful")
                
                # Test setting and getting a value
                r.set('celery_test', 'test_value')
                value = r.get('celery_test')
                logger.info(f"✅ Redis read/write test: {value}")
                r.delete('celery_test')
                
        except ImportError:
            logger.error("❌ Redis library not installed")
        except Exception as e:
            logger.error(f"❌ Redis connection failed: {e}")
    else:
        logger.info(f"Broker type not Redis: {broker_url}")

if __name__ == '__main__':
    print("🔍 Celery Diagnostic Test")
    print("=" * 50)
    
    test_broker_connection()
    print()
    test_celery_connectivity()
    
    print("\n" + "=" * 50)
    print("📋 TROUBLESHOOTING TIPS:")
    print("1. Make sure Redis is running: sudo systemctl status redis")
    print("2. Start Celery worker: python worker.py")
    print("3. Or use: celery -A app.celery_app worker --loglevel=info")
    print("4. Check if worker can import tasks: python -c 'from app.tasks import process_pdf_task'")
