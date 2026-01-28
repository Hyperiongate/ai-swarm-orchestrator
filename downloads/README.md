# 🛠️ Shiftwork Solutions Desktop Applications

**Professional Tools for Shift Operations Management**

This folder contains powerful desktop applications designed to help you optimize shift operations, analyze costs, and process survey data with professional-quality outputs.

---

## 📦 Available Applications

### 💰 Cost of Time Calculator v3.3.2
**Purpose:** Compare labor costs across different shift schedule configurations

**Key Features:**
- Calculate costs for 5-day/8-hour, 7-day/8-hour, and 7-day/12-hour schedules
- Real-time cost updates as inputs change
- Save multiple schedule calculations for comparison
- Staffing analysis with overtime scenarios
- Incentive cost analysis (extra days off, shift differential, vacation, overlap)
- Adverse cost analysis for understanding/overstaffing trade-offs
- Export to Excel and PDF with professional formatting
- Built-in explanations for all calculated fields

**File:** `cost_of_time_calculator_v3_3_2.pyw`

---

### 📋 Survey Processing App v87
**Purpose:** Extract questions from surveys, process response data, and generate professional reports

**Key Features:**
- Extract questions from Word survey documents
- Process Remark survey data or manual CSV imports
- Generate professional PDF crosstab reports
- Export to Excel spreadsheets with formulas
- Update PowerPoint templates with survey data
- Benchmark comparison capabilities
- Multiple breakout analysis options
- Percentages automatically sum to exactly 100%
- Professional formatting with company branding

**File:** `SurveySelector_v87_FINAL.pyw`

---

## 🚀 Quick Start Guide

### Step 1: Install Python

**Don't have Python?** Download from [python.org](https://www.python.org/downloads/)

#### Windows Installation:
1. Download Python 3.8 or higher from python.org
2. Run the installer
3. ✅ **IMPORTANT:** Check "Add Python to PATH"
4. Click "Install Now"
5. Restart your computer

#### macOS Installation:
```bash
# Using Homebrew (recommended)
brew install python3

# Or download installer from python.org
```

#### Linux Installation:
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install python3 python3-pip python3-tk

# Fedora/RHEL
sudo dnf install python3 python3-pip python3-tkinter
```

---

### Step 2: Install Required Packages

Open **Terminal** (Mac/Linux) or **Command Prompt** (Windows) and run:

#### Option A: Install Everything at Once (Recommended)
```bash
pip install -r requirements.txt
```

#### Option B: Install Packages Individually

**For Cost of Time Calculator:**
```bash
pip install matplotlib openpyxl reportlab
```

**For Survey Processing App:**
```bash
pip install pandas python-docx reportlab openpyxl python-pptx
```

---

### Step 3: Run the Applications

#### Windows:
1. Double-click the `.pyw` file
2. Application window will open (no console window)

#### macOS:
1. Right-click the `.pyw` file
2. Select "Open With" → "Python Launcher"
3. Or from Terminal:
   ```bash
   python3 cost_of_time_calculator_v3_3_2.pyw
   ```

#### Linux:
1. Make the file executable:
   ```bash
   chmod +x cost_of_time_calculator_v3_3_2.pyw
   ```
2. Double-click to run, or from terminal:
   ```bash
   python3 cost_of_time_calculator_v3_3_2.pyw
   ```

---

## 🆘 Troubleshooting

### "Python not found" or "'python' is not recognized"

**Solution:**
- Reinstall Python with "Add Python to PATH" checked
- Restart your computer after installation
- Try using `python3` instead of `python`

### "No module named 'tkinter'"

**Windows:** Tkinter should come with Python. Reinstall Python.

**macOS:**
```bash
brew install python-tk
```

**Linux:**
```bash
sudo apt-get install python3-tk
```

### "ModuleNotFoundError: No module named 'matplotlib'" (or other packages)

**Solution:**
- Run the pip install commands again
- Try `pip3` instead of `pip`:
  ```bash
  pip3 install matplotlib openpyxl reportlab
  ```
- If using virtual environment, activate it first

### Application won't start or crashes immediately

**Debugging steps:**
1. Open Terminal/Command Prompt
2. Navigate to the file location:
   ```bash
   cd Downloads
   ```
3. Run with Python directly:
   ```bash
   python cost_of_time_calculator_v3_3_2.pyw
   ```
4. Read the error messages that appear
5. Most common issues:
   - Missing packages → Run pip install commands
   - Wrong Python version → Need Python 3.8+
   - Missing tkinter → See "No module named tkinter" above

### Permission denied error (Mac/Linux)

**Solution:**
```bash
chmod +x cost_of_time_calculator_v3_3_2.pyw
```

---

## 📚 Application Usage Tips

### Cost of Time Calculator

1. **Start with Basic Inputs**
   - Enter base hourly rate
   - Set burden rates (benefits, taxes, etc.)
   - Define time off policies
   - Configure shift parameters

2. **Create Schedule Scenarios**
   - Use the Schedule Cost Calculator on the right
   - Save multiple scenarios for comparison
   - Compare different shift lengths and patterns

3. **Analyze Staffing Needs**
   - Go to "Staffing Analysis" tab
   - Input positions to cover
   - Review different overtime percentage scenarios
   - Examine incentive costs

4. **Export Results**
   - Save configurations for future use
   - Export to Excel for detailed analysis
   - Generate PDF reports for presentations

### Survey Processing App

1. **Load Your Survey**
   - Step 1: Select Word document with survey questions
   - Questions are automatically extracted

2. **Import Response Data**
   - Step 2: Load Remark data file or manual CSV
   - Select breakout variables for analysis

3. **Configure Analysis**
   - Step 3: Choose questions to include
   - Select crosstab breakouts
   - Add benchmark data if available

4. **Generate Reports**
   - Step 4: Create PDF reports with professional formatting
   - Export to Excel for further analysis
   - Update PowerPoint templates with data

---

## 📞 Support & Contact

**Need Help?**

- 📞 Phone: **(415) 763-5005**
- 🌐 Website: **[shift-work.com](https://shift-work.com)**
- 📧 Email: **info@shift-work.com**

With hundreds of successful projects across industries, Shiftwork Solutions specializes in helping organizations optimize their shift operations for maximum efficiency and employee satisfaction.

---

## 🔄 Updates & New Versions

**Current Versions:**
- Cost of Time Calculator: v3.3.2 (Updated January 12, 2026)
- Survey Processing App: v87 (Latest)

Check back regularly for updates and new features. When new versions are released, simply download and replace the old `.pyw` files.

---

## 📄 System Requirements Summary

| Requirement | Details |
|------------|---------|
| **Python Version** | 3.8 or higher (3.9+ recommended) |
| **Operating System** | Windows 10+, macOS 10.14+, Linux (Ubuntu 20.04+) |
| **RAM** | 4GB minimum, 8GB recommended |
| **Disk Space** | 100MB for applications + Python packages |
| **Display** | 1280x720 minimum resolution |

---

## 🔒 Privacy & Data Security

- **All processing happens locally** on your computer
- **No data is sent to external servers** (except for package installation)
- **Your survey data and calculations remain private**
- **Files are saved only where you choose**

---

## 📝 License & Copyright

**Copyright © 2025 Shiftwork Solutions LLC**  
All Rights Reserved

These applications are provided for use by Shiftwork Solutions clients and partners. Redistribution or modification without permission is prohibited.

---

## 🎯 Pro Tips

1. **Save Your Work Frequently**: Both apps have auto-save, but manual saves are recommended
2. **Use Descriptive Names**: When saving scenarios, use clear names like "Current_12hr_Schedule"
3. **Export Before Major Changes**: Create Excel/PDF backups before experimenting
4. **Keep Python Updated**: Run `python --version` to check your version
5. **Create Desktop Shortcuts**: For quick access to frequently used apps

---

**Built with care by Shiftwork Solutions LLC**  
*Helping organizations optimize shift operations since 1992*

---

<!-- I did no harm and this file is not truncated -->
