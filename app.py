import os
import logging
import tempfile
from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
import pyembroidery

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")

# Configuration
UPLOAD_FOLDER = tempfile.gettempdir()
ALLOWED_EXTENSIONS = {'pxf', 'dst', 'pes', 'jef', 'exp', 'vp3', 'hus', 'xxx'}  # Support more embroidery formats
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

def allowed_file(filename):
    """Check if file has allowed extension"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def try_pxf_analysis(file_path):
    """Try to extract basic information from PXF files using binary analysis"""
    try:
        with open(file_path, 'rb') as f:
            data = f.read()
        
        # Basic file information
        analysis = {
            'filename': os.path.basename(file_path),
            'file_size': len(data),
            'format_detected': 'PXF (PMLPXF variant)',
            'stitch_count': 'Unknown (requires conversion)',
            'thread_count': 0,
            'colors': [],
            'stitch_types': ['Format not fully supported'],
            'layers': [],
            'dimensions': None,
            'raw_analysis': True
        }
        
        # Try to extract some basic information from the binary data
        header_info = []
        
        # Check for PMLPXF header
        if data.startswith(b'PMLPXF01'):
            header_info.append('PMLPXF Version 1 format detected')
            
            # Try to find version and creation info
            try:
                # Look for "Created" string which often appears in PXF metadata
                created_pos = data.find(b'Created')
                if created_pos != -1:
                    # Extract some text around the "Created" marker
                    start = max(0, created_pos - 20)
                    end = min(len(data), created_pos + 100)
                    metadata = data[start:end]
                    try:
                        # Try to decode as text to extract readable info
                        metadata_str = metadata.decode('utf-8', errors='ignore')
                        if 'Created' in metadata_str:
                            header_info.append(f'Metadata found: {metadata_str[:50]}...')
                    except:
                        pass
                
                # Try to estimate thread count by looking for color patterns
                # PXF files often store RGB color values
                rgb_patterns = 0
                pos = 0
                while pos < len(data) - 3:
                    # Look for potential RGB triplets (values between 0-255)
                    if (data[pos] <= 255 and data[pos+1] <= 255 and data[pos+2] <= 255 and
                        data[pos] + data[pos+1] + data[pos+2] > 50):  # Not all zeros/very dark
                        rgb_patterns += 1
                        pos += 3
                    else:
                        pos += 1
                
                # Rough estimation of thread colors
                estimated_colors = min(rgb_patterns // 10, 20)  # Rough heuristic
                if estimated_colors > 0:
                    analysis['thread_count'] = f"~{estimated_colors} (estimated)"
                    for i in range(min(estimated_colors, 5)):
                        analysis['colors'].append({
                            'index': i + 1,
                            'color': 'Unknown',
                            'hex': 'N/A',
                            'description': 'Requires conversion for detailed info',
                            'brand': 'N/A'
                        })
                
            except Exception as e:
                logging.warning(f"Error in PXF analysis: {e}")
        
        analysis['layers'] = header_info if header_info else ['Basic file structure detected']
        
        # Add helpful conversion note
        analysis['conversion_note'] = 'Ten plik wymaga konwersji do formatu .dst, .pes lub .jef aby uzyskać pełne informacje o wzorze haftu.'
        
        return analysis
        
    except Exception as e:
        logging.error(f"Error in PXF binary analysis: {e}")
        return None

def analyze_embroidery_file(file_path):
    """Analyze embroidery file using multiple approaches"""
    try:
        # Log file information for debugging
        logging.info(f"Analyzing file: {file_path}")
        logging.info(f"File size: {os.path.getsize(file_path)} bytes")
        
        # Check if file exists and is not empty
        if not os.path.exists(file_path):
            return None, "File does not exist"
        
        if os.path.getsize(file_path) == 0:
            return None, "File is empty"
        
        file_ext = os.path.splitext(file_path)[1].lower()
        
        # Try to read the embroidery file with pyembroidery first
        pattern = pyembroidery.read(file_path)
        
        if pattern is None and file_ext == '.pxf':
            # For PXF files, try alternative analysis approaches
            pxf_analysis = try_pxf_analysis(file_path)
            if pxf_analysis:
                return pxf_analysis, None
            
            # If alternative analysis fails, check the header for error type
            with open(file_path, 'rb') as f:
                header = f.read(32)
                logging.info(f"File header (first 32 bytes): {header}")
            
            if header.startswith(b'PMLPXF'):
                return None, "pxf_unsupported_variant"
            else:
                return None, "pxf_invalid_structure"
        elif pattern is None:
            return None, f"Nie można odczytać pliku {file_ext}. Plik może być uszkodzony lub używać nieobsługiwanego wariantu formatu."
        
        # Extract basic information
        analysis = {
            'filename': os.path.basename(file_path),
            'stitch_count': len(pattern.stitches),
            'thread_count': len(pattern.threadlist),
            'colors': [],
            'stitch_types': [],
            'layers': [],
            'dimensions': None
        }
        
        # Extract thread colors
        for i, thread in enumerate(pattern.threadlist):
            color_info = {
                'index': i + 1,
                'color': thread.color if thread.color else 'Unknown',
                'hex': thread.hex if hasattr(thread, 'hex') and thread.hex else 'N/A',
                'description': thread.description if thread.description else 'N/A',
                'brand': thread.brand if thread.brand else 'N/A'
            }
            analysis['colors'].append(color_info)
        
        # Extract stitch types
        stitch_types = set()
        for stitch in pattern.stitches:
            if len(stitch) >= 3:  # x, y, command
                command = stitch[2]
                if command == pyembroidery.STITCH:
                    stitch_types.add('Normal Stitch')
                elif command == pyembroidery.JUMP:
                    stitch_types.add('Jump')
                elif command == pyembroidery.COLOR_CHANGE:
                    stitch_types.add('Color Change')
                elif command == pyembroidery.TRIM:
                    stitch_types.add('Trim')
                elif command == pyembroidery.END:
                    stitch_types.add('End')
                elif command == pyembroidery.COLOR_BREAK:
                    stitch_types.add('Color Break')
                elif command == pyembroidery.STITCH_BREAK:
                    stitch_types.add('Stitch Break')
                else:
                    stitch_types.add(f'Command {command}')
        
        analysis['stitch_types'] = list(stitch_types)
        
        # Get pattern dimensions
        extends = pattern.extends()
        if extends:
            width = extends[2] - extends[0]  # max_x - min_x
            height = extends[3] - extends[1]  # max_y - min_y
            analysis['dimensions'] = {
                'width': round(width / 10, 2),  # Convert to mm (assuming 0.1mm units)
                'height': round(height / 10, 2),
                'min_x': round(extends[0] / 10, 2),
                'min_y': round(extends[1] / 10, 2),
                'max_x': round(extends[2] / 10, 2),
                'max_y': round(extends[3] / 10, 2)
            }
        
        # Try to extract layer information (if available)
        # Note: Layer information might not be available in all PXF files
        if hasattr(pattern, 'extras') and pattern.extras:
            for key, value in pattern.extras.items():
                if 'layer' in key.lower():
                    analysis['layers'].append(f"{key}: {value}")
        
        if not analysis['layers']:
            analysis['layers'] = ['Layer information not available in this file']
        
        return analysis, None
        
    except Exception as e:
        logging.error(f"Error analyzing embroidery file: {str(e)}")
        return None, f"Error analyzing file: {str(e)}"

@app.route('/')
def index():
    """Main page with upload form"""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload and analysis"""
    if 'file' not in request.files:
        flash('No file selected', 'error')
        return redirect(url_for('index'))
    
    file = request.files['file']
    
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('index'))
    
    if not allowed_file(file.filename):
        flash('Invalid file type. Please upload a supported embroidery file (.pxf, .dst, .pes, .jef, .exp, .vp3, .hus, .xxx).', 'error')
        return redirect(url_for('index'))
    
    try:
        # Save file temporarily
        filename = secure_filename(file.filename)
        temp_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(temp_path)
        
        # Analyze the file
        analysis, error = analyze_embroidery_file(temp_path)
        
        # Clean up temporary file
        try:
            os.remove(temp_path)
        except OSError:
            logging.warning(f"Could not remove temporary file: {temp_path}")
        
        if error:
            if error == 'pxf_unsupported_variant':
                return render_template('pxf_error.html', 
                                     error_type='unsupported_variant',
                                     filename=filename)
            elif error == 'pxf_invalid_structure':
                return render_template('pxf_error.html', 
                                     error_type='invalid_structure',
                                     filename=filename)
            else:
                flash(f'Błąd podczas przetwarzania pliku: {error}', 'error')
                return redirect(url_for('index'))
        
        if analysis is None:
            flash('Nie można przeanalizować pliku hafciarskiego', 'error')
            return redirect(url_for('index'))
        
        return render_template('results.html', analysis=analysis)
        
    except Exception as e:
        logging.error(f"Upload error: {str(e)}")
        flash(f'An error occurred while processing the file: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.errorhandler(413)
def too_large(e):
    """Handle file too large error"""
    flash('File is too large. Maximum size is 16MB.', 'error')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
