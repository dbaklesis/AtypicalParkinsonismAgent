@echo off
:: Αλλαγή του working directory στον φάκελο του project
cd /d "C:\AtypicalParkinsonismAgent"

:: Δημιουργία του φακέλου logs αν δεν υπάρχει
if not exist "C:\AtypicalParkinsonismAgent\logs" mkdir "C:\AtypicalParkinsonismAgent\logs"

:: 1. Αλλαγή και Ενεργοποίηση του Virtual Environment
call "C:\AtypicalParkinsonismAgent\.venv\Scripts\activate.bat"

:: 2. Εκτέλεση Pipeline (PubMed + ClinicalTrials + Europe PMC + AI Screening + Summaries)
python "C:\AtypicalParkinsonismAgent\src\run_pipeline.py"  --screen-limit 100 --summary-limit 100 >> "C:\AtypicalParkinsonismAgent\logs\agent_execution.log" 2>&1

:: 3. Αποστολή Email Αναφοράς
python "C:\AtypicalParkinsonismAgent\src\send_report.py" >> "C:\AtypicalParkinsonismAgent\logs\agent_execution.log" 2>&1

:: 4. Απενεργοποίηση του Virtual Environment
call deactivate