from flask import Flask, render_template, request, jsonify
import google.generativeai as genai
import os
import json
from datetime import datetime
import secrets
import sqlite3

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.secret_key = secrets.token_hex(16)

# Configure Gemini API
genai.configure(api_key="AIzaSyCdTA9IGzgUq8k8ptRltG17v2V5C1BV2Qc")  # Replace with your key
model = genai.GenerativeModel('gemini-2.5-flash')

# Database setup
def init_db():
    conn = sqlite3.connect('cybercrime.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS cases
                 (id TEXT PRIMARY KEY,
                  name TEXT,
                  email TEXT,
                  phone TEXT,
                  description TEXT,
                  dateOccurred TEXT,
                  evidenceUrls TEXT,
                  category TEXT,
                  severity TEXT,
                  caseValue TEXT,
                  caseSummary TEXT,
                  analysisDescription TEXT,
                  preventionSteps TEXT,
                  immediateActions TEXT,
                  timestamp TEXT,
                  status TEXT,
                  dateOpened TEXT,
                  dateClosed TEXT,
                  assignedOfficer TEXT,
                  priority TEXT,
                  requestedOfficer INTEGER,
                  ipAddress TEXT)''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/results/<case_id>')
def results(case_id):
    return render_template('results.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/api/submit-report', methods=['POST'])
def submit_report():
    try:
        data = request.json
        print(f"Received data: {data}")
        
        # Analyze with Gemini
        prompt = f"""Analyze this cybercrime report and categorize it. Return ONLY a valid JSON object with no markdown formatting or backticks:

Report Details:
- Date Occurred: {data['dateOccurred']}
- Description: {data['description']}
- Evidence: {data.get('evidenceUrls', 'None provided')}

Return exactly this structure:
{{
  "category": "one of: Phishing, Identity Theft, Online Fraud, Hacking, Ransomware, Cyberbullying, Data Breach, Malware, Social Engineering, Other",
  "severity": "one of: Low, Moderate, Critical",
  "description": "brief 2-3 sentence professional description of what happened",
  "caseValue": "estimated impact/value in RM (e.g., 'RM 5,000' or 'Data compromise')",
  "caseSummary": "detailed 3-4 sentence summary for investigation officers",
  "preventionSteps": ["step 1", "step 2", "step 3", "step 4", "step 5"],
  "immediateActions": ["action 1", "action 2", "action 3", "action 4"]
}}"""
        
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        print(f"AI Response: {response_text}")
        
        # Clean response
        response_text = response_text.replace('```json', '').replace('```', '').strip()
        if response_text.startswith('{') and response_text.endswith('}'):
            analysis = json.loads(response_text)
        else:
            start = response_text.find('{')
            end = response_text.rfind('}') + 1
            analysis = json.loads(response_text[start:end])
        
        # Create case
        case_id = f"CASE{int(datetime.now().timestamp())}"
        print(f"Creating case: {case_id}")
        
        # Save to database
        conn = sqlite3.connect('cybercrime.db')
        c = conn.cursor()
        c.execute('''INSERT INTO cases VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                  (case_id,
                   data['name'],
                   data['email'],
                   data['phone'],
                   data['description'],
                   data['dateOccurred'],
                   data.get('evidenceUrls', ''),
                   analysis['category'],
                   analysis['severity'],
                   analysis.get('caseValue', 'To be determined'),
                   analysis.get('caseSummary', analysis['description']),
                   analysis['description'],
                   json.dumps(analysis['preventionSteps']),
                   json.dumps(analysis['immediateActions']),
                   datetime.now().isoformat(),
                   'Open',
                   datetime.now().strftime('%Y-%m-%d'),
                   None,
                   'Pending Assignment',
                   'High' if analysis['severity'] == 'Critical' else 'Medium' if analysis['severity'] == 'Moderate' else 'Low',
                   0,
                   request.remote_addr))
        conn.commit()
        conn.close()
        
        print(f"Case saved to database")
        
        return jsonify({
            'success': True,
            'caseId': case_id,
            'analysis': analysis
        })
        
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        case_id = data.get('caseId')
        message_text = data['message']
        
        # Get case category from database
        conn = sqlite3.connect('cybercrime.db')
        c = conn.cursor()
        c.execute("SELECT category FROM cases WHERE id=?", (case_id,))
        result = c.fetchone()
        conn.close()
        
        category = result[0] if result else 'cybercrime'
        
        prompt = f"""You are a helpful cybercrime support assistant for SalamCyber, a Petronas initiative.

The user has reported a {category} incident. 

Important contact information:
- Cybercrime Hotline: 1-800-CYBER-MY (24/7 Support)
- Email: support@pythoncyber.my
- Emergency: If life-threatening, call 999

Answer their question helpfully, professionally, and supportively. If they ask for contact information, provide the hotline above.

User question: {message_text}"""
        
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        return jsonify({
            'success': True,
            'response': response_text
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/request-officer', methods=['POST'])
def request_officer():
    try:
        data = request.json
        case_id = data['caseId']
        
        conn = sqlite3.connect('cybercrime.db')
        c = conn.cursor()
        c.execute("UPDATE cases SET requestedOfficer=1, status='Officer Requested' WHERE id=?", (case_id,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/cases', methods=['GET'])
def get_cases():
    try:
        conn = sqlite3.connect('cybercrime.db')
        c = conn.cursor()
        c.execute("SELECT * FROM cases")
        rows = c.fetchall()
        conn.close()
        
        cases = []
        for row in rows:
            cases.append({
                'id': row[0],
                'name': row[1],
                'email': row[2],
                'phone': row[3],
                'description': row[4],
                'dateOccurred': row[5],
                'evidenceUrls': row[6],
                'category': row[7],
                'severity': row[8],
                'caseValue': row[9],
                'caseSummary': row[10],
                'analysisDescription': row[11],
                'preventionSteps': json.loads(row[12]),
                'immediateActions': json.loads(row[13]),
                'timestamp': row[14],
                'status': row[15],
                'dateOpened': row[16],
                'dateClosed': row[17],
                'assignedOfficer': row[18],
                'priority': row[19],
                'requestedOfficer': bool(row[20]),
                'ipAddress': row[21]
            })
        
        return jsonify({
            'success': True,
            'cases': cases
        })
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/case/<case_id>', methods=['GET'])
def get_case(case_id):
    try:
        conn = sqlite3.connect('cybercrime.db')
        c = conn.cursor()
        c.execute("SELECT * FROM cases WHERE id=?", (case_id,))
        row = c.fetchone()
        conn.close()
        
        if row:
            case = {
                'id': row[0],
                'name': row[1],
                'email': row[2],
                'phone': row[3],
                'description': row[4],
                'dateOccurred': row[5],
                'evidenceUrls': row[6],
                'category': row[7],
                'severity': row[8],
                'caseValue': row[9],
                'caseSummary': row[10],
                'analysisDescription': row[11],
                'preventionSteps': json.loads(row[12]),
                'immediateActions': json.loads(row[13]),
                'timestamp': row[14],
                'status': row[15],
                'dateOpened': row[16],
                'dateClosed': row[17],
                'assignedOfficer': row[18],
                'priority': row[19],
                'requestedOfficer': bool(row[20]),
                'ipAddress': row[21]
            }
            return jsonify({'success': True, 'case': case})
        
        return jsonify({'success': False, 'error': 'Case not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/update-status', methods=['POST'])
def update_status():
    try:
        data = request.json
        case_id = data['caseId']
        new_status = data['status']
        
        conn = sqlite3.connect('cybercrime.db')
        c = conn.cursor()
        
        if new_status == 'Resolved':
            c.execute("UPDATE cases SET status=?, dateClosed=? WHERE id=?", 
                     (new_status, datetime.now().strftime('%Y-%m-%d'), case_id))
        else:
            c.execute("UPDATE cases SET status=? WHERE id=?", (new_status, case_id))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/assign-officer', methods=['POST'])
def assign_officer():
    try:
        data = request.json
        case_id = data['caseId']
        officer_name = data['officerName']
        
        conn = sqlite3.connect('cybercrime.db')
        c = conn.cursor()
        c.execute("UPDATE cases SET assignedOfficer=? WHERE id=?", (officer_name, case_id))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)