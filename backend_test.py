#!/usr/bin/env python3
"""
Backend API Testing for Telegram Housing Search WebApp
Tests all FastAPI endpoints with comprehensive validation
"""

import requests
import sys
import json
from datetime import datetime
from typing import Dict, Any

class TelegramHousingAPITester:
    def __init__(self, base_url="https://355833bb-8a05-4dc5-af42-67ba284efdd4.preview.emergentagent.com"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.test_telegram_id = 123456789
        self.test_property_id = None

    def run_test(self, name: str, method: str, endpoint: str, expected_status: int, 
                 data: Dict = None, params: Dict = None, validate_response: callable = None) -> tuple:
        """Run a single API test with comprehensive validation"""
        url = f"{self.base_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {method} {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=10)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, timeout=10)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=10)

            success = response.status_code == expected_status
            response_data = {}
            
            try:
                response_data = response.json() if response.content else {}
            except json.JSONDecodeError:
                response_data = {"raw_response": response.text}

            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                
                # Run custom validation if provided
                if validate_response and response_data:
                    validation_result = validate_response(response_data)
                    if not validation_result:
                        print(f"⚠️  Warning: Response validation failed")
                        success = False
                    else:
                        print(f"✅ Response validation passed")
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                if response_data:
                    print(f"   Response: {json.dumps(response_data, indent=2)}")

            return success, response_data

        except requests.exceptions.Timeout:
            print(f"❌ Failed - Request timeout")
            return False, {}
        except requests.exceptions.ConnectionError:
            print(f"❌ Failed - Connection error")
            return False, {}
        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def validate_health_response(self, response: Dict) -> bool:
        """Validate health check response"""
        return (
            response.get("status") == "healthy" and
            "service" in response and
            "Telegram Housing Search" in response.get("service", "")
        )

    def validate_metro_stations_response(self, response: Dict) -> bool:
        """Validate metro stations response"""
        if not isinstance(response, list):
            print(f"   Expected list, got {type(response)}")
            return False
        
        if len(response) != 15:
            print(f"   Expected 15 stations, got {len(response)}")
            return False
        
        # Check first station structure
        if response:
            station = response[0]
            required_fields = ['id', 'name', 'location', 'line', 'line_color']
            for field in required_fields:
                if field not in station:
                    print(f"   Missing field '{field}' in station")
                    return False
            
            # Check location structure
            location = station.get('location', {})
            if location.get('type') != 'Point' or 'coordinates' not in location:
                print(f"   Invalid location structure")
                return False
                
        return True

    def validate_properties_response(self, response: Dict) -> bool:
        """Validate properties search response"""
        if not isinstance(response, list):
            print(f"   Expected list, got {type(response)}")
            return False
        
        print(f"   Found {len(response)} properties")
        
        # If properties exist, validate structure
        if response:
            prop = response[0]
            required_fields = ['title', 'price', 'address']
            for field in required_fields:
                if field not in prop:
                    print(f"   Missing field '{field}' in property")
                    return False
            
            # Store first property ID for like test
            if 'id' in prop:
                self.test_property_id = prop['id']
                print(f"   Stored property ID for like test: {self.test_property_id}")
            elif 'source_url' in prop:
                # Generate a test property ID from source URL
                import hashlib
                self.test_property_id = hashlib.md5(prop['source_url'].encode()).hexdigest()[:8]
                print(f"   Generated property ID for like test: {self.test_property_id}")
                
        return True

    def validate_profile_response(self, response: Dict) -> bool:
        """Validate profile creation response"""
        return "success" in response and response.get("success") is True

    def validate_user_profile_response(self, response: Dict) -> bool:
        """Validate user profile retrieval response"""
        required_fields = ['telegram_id', 'name']
        for field in required_fields:
            if field not in response:
                print(f"   Missing field '{field}' in profile")
                return False
        return True

    def validate_like_response(self, response: Dict) -> bool:
        """Validate property like response"""
        return (
            response.get("success") is True and
            "message" in response
        )

    def test_health_check(self):
        """Test health check endpoint"""
        return self.run_test(
            "Health Check",
            "GET",
            "api/health",
            200,
            validate_response=self.validate_health_response
        )

    def test_metro_stations(self):
        """Test metro stations endpoint"""
        return self.run_test(
            "Metro Stations",
            "GET",
            "api/metro-stations",
            200,
            validate_response=self.validate_metro_stations_response
        )

    def test_properties_near_metro(self):
        """Test properties near metro endpoint"""
        return self.run_test(
            "Properties Near Metro (Lubyanka)",
            "GET",
            "api/properties/near-metro",
            200,
            params={"station_name": "Lubyanka", "radius_km": 2.0},
            validate_response=self.validate_properties_response
        )

    def test_properties_near_metro_english(self):
        """Test properties near metro with English station name"""
        return self.run_test(
            "Properties Near Metro (English name)",
            "GET",
            "api/properties/near-metro",
            200,
            params={"station_name": "Teatralnaya", "radius_km": 1.0},
            validate_response=self.validate_properties_response
        )

    def test_create_user_profile(self):
        """Test user profile creation"""
        profile_data = {
            "telegram_id": self.test_telegram_id,
            "name": "Иван Тестов",
            "gender": "male",
            "age": 25,
            "about": "Ищу квартиру в центре Москвы",
            "preferred_location": "Центр",
            "search_radius_km": 2.0
        }
        
        return self.run_test(
            "Create User Profile",
            "POST",
            "api/user/profile",
            200,
            data=profile_data,
            validate_response=self.validate_profile_response
        )

    def test_get_user_profile(self):
        """Test user profile retrieval"""
        return self.run_test(
            "Get User Profile",
            "GET",
            f"api/user/profile/{self.test_telegram_id}",
            200,
            validate_response=self.validate_user_profile_response
        )

    def test_like_property(self):
        """Test property liking functionality"""
        if not self.test_property_id:
            print("⚠️  Skipping like test - no property ID available")
            return True, {}
            
        like_data = {
            "property_id": self.test_property_id,
            "telegram_id": self.test_telegram_id
        }
        
        return self.run_test(
            "Like Property",
            "POST",
            f"api/properties/{self.test_property_id}/like",
            200,
            data=like_data,
            validate_response=self.validate_like_response
        )

    def test_invalid_metro_station(self):
        """Test invalid metro station handling"""
        return self.run_test(
            "Invalid Metro Station",
            "GET",
            "api/properties/near-metro",
            404,
            params={"station_name": "NonExistentStation", "radius_km": 2.0}
        )

    def test_invalid_user_profile(self):
        """Test invalid user profile retrieval"""
        return self.run_test(
            "Invalid User Profile",
            "GET",
            "api/user/profile/999999999",
            404
        )

def main():
    """Run all backend API tests"""
    print("🚀 Starting Telegram Housing Search API Tests")
    print("=" * 60)
    
    tester = TelegramHousingAPITester()
    
    # Core functionality tests
    print("\n📋 CORE API TESTS")
    print("-" * 30)
    
    tester.test_health_check()
    tester.test_metro_stations()
    tester.test_properties_near_metro()
    tester.test_properties_near_metro_english()
    
    # User profile tests
    print("\n👤 USER PROFILE TESTS")
    print("-" * 30)
    
    tester.test_create_user_profile()
    tester.test_get_user_profile()
    
    # Property interaction tests
    print("\n🏠 PROPERTY INTERACTION TESTS")
    print("-" * 30)
    
    tester.test_like_property()
    
    # Error handling tests
    print("\n❌ ERROR HANDLING TESTS")
    print("-" * 30)
    
    tester.test_invalid_metro_station()
    tester.test_invalid_user_profile()
    
    # Final results
    print("\n" + "=" * 60)
    print(f"📊 TEST RESULTS")
    print(f"Tests run: {tester.tests_run}")
    print(f"Tests passed: {tester.tests_passed}")
    print(f"Tests failed: {tester.tests_run - tester.tests_passed}")
    print(f"Success rate: {(tester.tests_passed / tester.tests_run * 100):.1f}%")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 All tests passed!")
        return 0
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
        return 1

if __name__ == "__main__":
    sys.exit(main())