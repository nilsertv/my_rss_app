"""
Script de prueba para verificar el servidor web
"""
import requests
import json

BASE_URL = "http://localhost:8080"

def test_endpoints():
    print("🧪 Probando endpoints del servidor web...\n")
    
    # Test 1: Info endpoint
    print("1️⃣ Probando GET /")
    try:
        response = requests.get(f"{BASE_URL}/")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {json.dumps(response.json(), indent=2)}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    print()
    
    # Test 2: Health endpoint
    print("2️⃣ Probando GET /health")
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {json.dumps(response.json(), indent=2)}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    print()
    
    # Test 3: Feed endpoint
    print("3️⃣ Probando GET /feed")
    try:
        response = requests.get(f"{BASE_URL}/feed")
        print(f"   Status: {response.status_code}")
        print(f"   Content-Type: {response.headers.get('Content-Type')}")
        if response.status_code == 200:
            print(f"   Feed size: {len(response.content)} bytes")
            print(f"   First 200 chars: {response.text[:200]}...")
        else:
            print(f"   Response: {response.text}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    print()
    
    # Test 4: Feed.xml endpoint (alias)
    print("4️⃣ Probando GET /feed.xml")
    try:
        response = requests.get(f"{BASE_URL}/feed.xml")
        print(f"   Status: {response.status_code}")
        print(f"   Content-Type: {response.headers.get('Content-Type')}")
        if response.status_code == 200:
            print(f"   Feed size: {len(response.content)} bytes")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    print()
    
    print("✅ Pruebas completadas!")

if __name__ == "__main__":
    print("=" * 60)
    print("Test del Servidor Web RSS")
    print("=" * 60)
    print()
    
    try:
        test_endpoints()
    except KeyboardInterrupt:
        print("\n\n⏸️  Pruebas interrumpidas por el usuario")
    except Exception as e:
        print(f"\n\n❌ Error general: {e}")
