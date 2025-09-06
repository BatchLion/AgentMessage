#!/usr/bin/env python3
"""
AgentMessage Remote API Test Suite

This script provides comprehensive testing for the AgentMessage remote database API.
It tests all endpoints, error handling, and data validation.
"""

import requests
import json
import time
import sys
from typing import Dict, Any, Optional
from datetime import datetime
from urllib3.exceptions import InsecureRequestWarning

# Disable SSL warnings for self-signed certificates
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

class AgentMessageAPITester:
    def __init__(self, base_url: str = "https://battalions.cloud:8443", verify_ssl: bool = False):
        self.base_url = base_url.rstrip('/')
        self.verify_ssl = verify_ssl
        self.session = requests.Session()
        self.session.verify = verify_ssl
        self.test_results = []
        self.test_dids = []
        
    def log_test(self, test_name: str, success: bool, details: str = ""):
        """Log test result"""
        status = "✓ PASS" if success else "✗ FAIL"
        timestamp = datetime.now().strftime("%H:%M:%S")
        result = f"[{timestamp}] {status} - {test_name}"
        if details:
            result += f" | {details}"
        print(result)
        self.test_results.append((test_name, success, details))
        
    def make_request(self, method: str, endpoint: str, data: Optional[Dict] = None, 
                    expected_status: int = 200) -> tuple[bool, Dict[str, Any], int]:
        """Make API request and return success, response data, status code"""
        url = f"{self.base_url}{endpoint}"
        
        try:
            if method.upper() == 'GET':
                response = self.session.get(url)
            elif method.upper() == 'POST':
                response = self.session.post(url, json=data)
            elif method.upper() == 'PUT':
                response = self.session.put(url, json=data)
            elif method.upper() == 'DELETE':
                response = self.session.delete(url)
            else:
                return False, {"error": f"Unsupported method: {method}"}, 0
                
            try:
                response_data = response.json()
            except json.JSONDecodeError:
                response_data = {"raw_response": response.text}
                
            success = response.status_code == expected_status
            return success, response_data, response.status_code
            
        except requests.exceptions.RequestException as e:
            return False, {"error": str(e)}, 0
    
    def test_health_check(self):
        """Test health check endpoint"""
        print("\n=== Health Check Test ===")
        success, data, status = self.make_request('GET', '/health', expected_status=200)
        
        if success and data.get('status') == 'healthy':
            self.log_test("Health Check", True, f"Service is healthy")
        else:
            self.log_test("Health Check", False, f"Status: {status}, Data: {data}")
            
    def test_list_empty_identities(self):
        """Test listing identities when database is empty"""
        print("\n=== List Empty Identities Test ===")
        success, data, status = self.make_request('GET', '/identities', expected_status=200)
        
        if success and isinstance(data.get('identities'), list):
            count = len(data['identities'])
            self.log_test("List Empty Identities", True, f"Found {count} identities")
        else:
            self.log_test("List Empty Identities", False, f"Status: {status}, Data: {data}")
            
    def test_create_identity(self, did: str, name: str, description: str, capabilities: list):
        """Test creating an identity"""
        identity_data = {
            "did": did,
            "name": name,
            "description": description,
            "capabilities": capabilities
        }
        
        success, data, status = self.make_request('POST', '/identities', 
                                                 data=identity_data, expected_status=201)
        
        if success and data.get('message'):
            self.log_test(f"Create Identity ({name})", True, f"DID: {did}")
            self.test_dids.append(did)
            return True
        else:
            self.log_test(f"Create Identity ({name})", False, f"Status: {status}, Data: {data}")
            return False
            
    def test_get_identity(self, did: str, should_exist: bool = True):
        """Test getting a specific identity"""
        expected_status = 200 if should_exist else 404
        success, data, status = self.make_request('GET', f'/identities/{did}', 
                                                 expected_status=expected_status)
        
        test_name = f"Get Identity ({did[:20]}...)"
        if should_exist:
            if success and data.get('success') and data.get('did') == did:
                self.log_test(test_name, True, f"Found identity: {data.get('name')}")
                return True
            else:
                self.log_test(test_name, False, f"Status: {status}, Data: {data}")
                return False
        else:
            if status == 404:
                self.log_test(test_name + " (Not Found)", True, "Correctly returned 404")
                return True
            else:
                self.log_test(test_name + " (Not Found)", False, f"Expected 404, got {status}")
                return False
                
    def test_update_identity(self, did: str, updated_data: Dict):
        """Test updating an identity"""
        success, data, status = self.make_request('PUT', f'/identities/{did}', 
                                                 data=updated_data, expected_status=200)
        
        if success and data.get('message'):
            self.log_test(f"Update Identity ({did[:20]}...)", True, "Successfully updated")
            return True
        else:
            self.log_test(f"Update Identity ({did[:20]}...)", False, f"Status: {status}, Data: {data}")
            return False
            
    def test_delete_identity(self, did: str):
        """Test deleting an identity"""
        success, data, status = self.make_request('DELETE', f'/identities/{did}', 
                                                 expected_status=200)
        
        if success and data.get('message'):
            self.log_test(f"Delete Identity ({did[:20]}...)", True, "Successfully deleted")
            if did in self.test_dids:
                self.test_dids.remove(did)
            return True
        else:
            self.log_test(f"Delete Identity ({did[:20]}...)", False, f"Status: {status}, Data: {data}")
            return False
            
    def test_list_identities_with_pagination(self):
        """Test listing identities with pagination"""
        print("\n=== Pagination Tests ===")
        
        # Test with limit
        success, data, status = self.make_request('GET', '/identities?limit=1', expected_status=200)
        if success and isinstance(data.get('identities'), list):
            count = len(data['identities'])
            total = data.get('total', 0)
            self.log_test("Pagination (limit=1)", True, f"Returned {count} of {total} identities")
        else:
            self.log_test("Pagination (limit=1)", False, f"Status: {status}, Data: {data}")
            
        # Test with offset
        success, data, status = self.make_request('GET', '/identities?limit=1&offset=1', expected_status=200)
        if success and isinstance(data.get('identities'), list):
            count = len(data['identities'])
            self.log_test("Pagination (offset=1)", True, f"Returned {count} identities with offset")
        else:
            self.log_test("Pagination (offset=1)", False, f"Status: {status}, Data: {data}")
            
    def test_error_handling(self):
        """Test various error conditions"""
        print("\n=== Error Handling Tests ===")
        
        # Test invalid JSON
        try:
            response = self.session.post(f"{self.base_url}/identities", 
                                       data="{invalid json}", 
                                       headers={'Content-Type': 'application/json'})
            if response.status_code == 400:
                self.log_test("Invalid JSON", True, "Correctly rejected invalid JSON")
            else:
                self.log_test("Invalid JSON", False, f"Expected 400, got {response.status_code}")
        except Exception as e:
            self.log_test("Invalid JSON", False, f"Exception: {e}")
            
        # Test missing required fields
        incomplete_data = {"name": "Incomplete Agent"}
        success, data, status = self.make_request('POST', '/identities', 
                                                 data=incomplete_data, expected_status=400)
        if status == 400:
            self.log_test("Missing Required Fields", True, "Correctly rejected incomplete data")
        else:
            self.log_test("Missing Required Fields", False, f"Expected 400, got {status}")
            
    def cleanup_test_data(self):
        """Clean up any remaining test data"""
        print("\n=== Cleanup ===")
        for did in self.test_dids.copy():
            self.test_delete_identity(did)
            
    def run_full_test_suite(self):
        """Run the complete test suite"""
        print("=== AgentMessage Remote API Test Suite ===")
        print(f"API Base URL: {self.base_url}")
        print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Generate unique test DIDs
        timestamp = int(time.time())
        test_did_1 = f"did:test:agent_{timestamp}_1"
        test_did_2 = f"did:test:agent_{timestamp}_2"
        
        try:
            # Basic functionality tests
            self.test_health_check()
            self.test_list_empty_identities()
            
            # CRUD operations
            print("\n=== CRUD Operations Tests ===")
            self.test_create_identity(
                test_did_1, 
                "Test Agent 1", 
                "A test agent for API testing",
                ["chat", "code", "search"]
            )
            
            self.test_create_identity(
                test_did_2,
                "Test Agent 2", 
                "Another test agent for API testing",
                ["analysis", "translation"]
            )
            
            self.test_get_identity(test_did_1, should_exist=True)
            self.test_get_identity("did:test:nonexistent", should_exist=False)
            
            # Update test
            updated_data = {
                "did": test_did_1,
                "name": "Updated Test Agent 1",
                "description": "An updated test agent",
                "capabilities": ["chat", "code", "search", "debugging"]
            }
            self.test_update_identity(test_did_1, updated_data)
            self.test_get_identity(test_did_1, should_exist=True)  # Verify update
            
            # Pagination tests
            self.test_list_identities_with_pagination()
            
            # Error handling tests
            self.test_error_handling()
            
        finally:
            # Always cleanup
            self.cleanup_test_data()
            
        # Print summary
        self.print_test_summary()
        
    def print_test_summary(self):
        """Print test results summary"""
        print("\n=== Test Summary ===")
        total_tests = len(self.test_results)
        passed_tests = sum(1 for _, success, _ in self.test_results if success)
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests*100):.1f}%")
        
        if failed_tests > 0:
            print("\nFailed Tests:")
            for test_name, success, details in self.test_results:
                if not success:
                    print(f"  - {test_name}: {details}")
                    
        print(f"\nTest completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        return failed_tests == 0

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='AgentMessage API Test Suite')
    parser.add_argument('--url', default='https://battalions.cloud:8443', 
                       help='API base URL (default: https://battalions.cloud:8443)')
    parser.add_argument('--verify-ssl', action='store_true', 
                       help='Verify SSL certificates (default: False for self-signed certs)')
    parser.add_argument('--quick', action='store_true', 
                       help='Run quick tests only')
    
    args = parser.parse_args()
    
    tester = AgentMessageAPITester(args.url, verify_ssl=args.verify_ssl)
    
    if args.quick:
        # Quick tests
        tester.test_health_check()
        tester.test_list_empty_identities()
        success = len([r for r in tester.test_results if not r[1]]) == 0
    else:
        # Full test suite
        success = tester.run_full_test_suite()
    
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()