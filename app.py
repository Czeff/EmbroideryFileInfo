import os
import logging
import tempfile
from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix
import pyembroidery

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)  # needed for url_for to generate with https

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
    """Try to extract detailed information from PXF files using advanced binary analysis"""
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
            'raw_analysis': True,
            'detailed_info': {}
        }
        
        # Advanced binary analysis for more detailed extraction
        header_info = []
        detailed_info = {}
        
        # Check for PMLPXF header and extract detailed information
        if data.startswith(b'PMLPXF01'):
            header_info.append('PMLPXF Version 1 format detected')
            
            try:
                # Extract file header information (first 64 bytes contain important data)
                header = data[:64]
                
                # Try to extract design dimensions from header
                # PMLPXF stores dimensions in specific byte positions
                if len(header) >= 32:
                    # Extract potential width/height values (little-endian format)
                    import struct
                    try:
                        # Common positions for dimension data in PMLPXF
                        val1 = struct.unpack('<I', header[8:12])[0]  # Position 8-11
                        val2 = struct.unpack('<I', header[12:16])[0]  # Position 12-15
                        val3 = struct.unpack('<I', header[16:20])[0]  # Position 16-19
                        val4 = struct.unpack('<I', header[20:24])[0]  # Position 20-23
                        
                        # Filter reasonable dimension values (in 0.1mm units)
                        reasonable_dims = [v for v in [val1, val2, val3, val4] if 100 < v < 1000000]
                        if len(reasonable_dims) >= 2:
                            width_mm = reasonable_dims[0] / 10.0
                            height_mm = reasonable_dims[1] / 10.0
                            detailed_info['estimated_dimensions'] = f"{width_mm:.1f} × {height_mm:.1f} mm"
                            
                    except struct.error:
                        pass
                
                # Look for software version and creation info
                created_pos = data.find(b'Created')
                if created_pos != -1:
                    # Extract metadata around "Created" marker
                    start = max(0, created_pos - 30)
                    end = min(len(data), created_pos + 150)
                    metadata = data[start:end]
                    try:
                        metadata_str = metadata.decode('utf-8', errors='ignore')
                        # Extract software information
                        if 'Tajima' in metadata_str:
                            detailed_info['software'] = 'Tajima DG/ML by Pulse'
                        elif 'Pulse' in metadata_str:
                            detailed_info['software'] = 'Pulse Software'
                        
                        # Extract version if present
                        import re
                        version_match = re.search(r'DG(\d+)', metadata_str)
                        if version_match:
                            detailed_info['software_version'] = f"DG{version_match.group(1)}"
                            
                        header_info.append(f'Software: {detailed_info.get("software", "Unknown")}')
                        
                    except:
                        pass
                
                # Analyze pattern complexity by looking for stitch patterns
                stitch_patterns = 0
                jump_patterns = 0
                
                # Look for common stitch command patterns in PXF files
                for i in range(0, len(data) - 4, 4):
                    try:
                        # PXF stores coordinates and commands in 4-byte chunks
                        chunk = data[i:i+4]
                        if len(chunk) == 4:
                            # Look for coordinate patterns (reasonable X,Y values)
                            x = struct.unpack('<h', chunk[:2])[0] if len(chunk) >= 2 else 0
                            y = struct.unpack('<h', chunk[2:])[0] if len(chunk) >= 2 else 0
                            
                            # Count potential stitch coordinates
                            if -5000 < x < 5000 and -5000 < y < 5000:
                                stitch_patterns += 1
                                
                            # Look for jump patterns (larger coordinate changes)
                            if abs(x) > 1000 or abs(y) > 1000:
                                jump_patterns += 1
                                
                    except (struct.error, IndexError):
                        continue
                
                # Estimate stitch count based on pattern analysis
                if stitch_patterns > 0:
                    estimated_stitches = min(stitch_patterns // 4, 50000)  # Conservative estimate
                    if estimated_stitches > 100:
                        analysis['stitch_count'] = f"~{estimated_stitches:,} (estimated)"
                        detailed_info['estimated_stitches'] = estimated_stitches
                
                # Estimate pattern density
                if stitch_patterns > 0 and 'estimated_dimensions' in detailed_info:
                    try:
                        dims = detailed_info['estimated_dimensions'].split('×')
                        area = float(dims[0].strip()) * float(dims[1].replace('mm', '').strip())
                        if area > 0:
                            density = estimated_stitches / area
                            detailed_info['stitch_density'] = f"{density:.1f} stitches/cm²"
                    except:
                        pass
                
                # Estimate embroidery type based on patterns
                if stitch_patterns > 0:
                    jump_ratio = jump_patterns / stitch_patterns if stitch_patterns > 0 else 0
                    if jump_ratio > 0.3:
                        detailed_info['pattern_type'] = 'Complex design with fills and details'
                    elif jump_ratio > 0.1:
                        detailed_info['pattern_type'] = 'Medium complexity design'
                    else:
                        detailed_info['pattern_type'] = 'Simple outline or text design'
                
                # Advanced color analysis - look for RGB patterns
                colors_found = []
                pos = 0
                while pos < len(data) - 6 and len(colors_found) < 20:
                    # Look for RGB color patterns (3 consecutive bytes with reasonable values)
                    if (pos + 2 < len(data) and 
                        data[pos] <= 255 and data[pos+1] <= 255 and data[pos+2] <= 255):
                        
                        r, g, b = data[pos], data[pos+1], data[pos+2]
                        # Skip very dark colors (likely not thread colors)
                        if r + g + b > 50:
                            hex_color = f"#{r:02X}{g:02X}{b:02X}"
                            if hex_color not in [c['hex'] for c in colors_found]:
                                color_name = get_color_name(r, g, b)
                                colors_found.append({
                                    'hex': hex_color,
                                    'name': color_name,
                                    'rgb': f"RGB({r},{g},{b})"
                                })
                        pos += 3
                    else:
                        pos += 1
                
                # Update thread count and colors
                if colors_found:
                    analysis['thread_count'] = f"{len(colors_found)} (detected)"
                    for i, color in enumerate(colors_found[:10]):  # Limit to first 10 colors
                        analysis['colors'].append({
                            'index': i + 1,
                            'color': color['name'],
                            'hex': color['hex'],
                            'description': f"Detected color: {color['rgb']}",
                            'brand': 'Unknown'
                        })
                
                # Estimate thread length based on stitch count
                if 'estimated_stitches' in detailed_info:
                    # Average stitch length in embroidery is about 2-4mm
                    estimated_length = (detailed_info['estimated_stitches'] * 3) / 10  # in cm
                    if estimated_length > 100:
                        detailed_info['estimated_thread_length'] = f"{estimated_length/100:.1f} m"
                    else:
                        detailed_info['estimated_thread_length'] = f"{estimated_length:.0f} cm"
                
            except Exception as e:
                logging.warning(f"Error in advanced PXF analysis: {e}")
        
        # Compile layer information
        analysis['layers'] = header_info if header_info else ['Basic file structure detected']
        analysis['detailed_info'] = detailed_info
        
        # Enhanced conversion note
        analysis['conversion_note'] = 'Ten plik wymaga konwersji do formatu .dst, .pes lub .jef aby uzyskać pełne informacje o wzorze haftu.'
        
        return analysis
        
    except Exception as e:
        logging.error(f"Error in PXF binary analysis: {e}")
        return None

def get_color_name(r, g, b):
    """Get approximate color name from RGB values"""
    # Simple color name mapping
    if r > 200 and g < 100 and b < 100:
        return "Red"
    elif r < 100 and g > 200 and b < 100:
        return "Green"
    elif r < 100 and g < 100 and b > 200:
        return "Blue"
    elif r > 200 and g > 200 and b < 100:
        return "Yellow"
    elif r > 150 and g < 100 and b > 150:
        return "Purple"
    elif r < 100 and g > 150 and b > 150:
        return "Cyan"
    elif r > 200 and g > 100 and b < 100:
        return "Orange"
    elif r > 200 and g > 200 and b > 200:
        return "White"
    elif r < 50 and g < 50 and b < 50:
        return "Black"
    elif 100 < r < 200 and 100 < g < 200 and 100 < b < 200:
        return "Gray"
    else:
        return "Unknown"

def analyze_stitch_details(pattern):
    """Analyze detailed stitch information"""
    stats = {
        'total_stitches': len(pattern.stitches),
        'stitch_commands': {},
        'jump_count': 0,
        'color_changes': 0,
        'trims': 0,
        'max_jump_distance': 0,
        'avg_stitch_length': 0,
        'total_thread_length': 0,
        'stitch_density_analysis': {}
    }
    
    if len(pattern.stitches) == 0:
        return stats
    
    # Count different stitch types and calculate distances
    prev_x, prev_y = None, None
    stitch_distances = []
    jump_distances = []
    
    for stitch in pattern.stitches:
        if len(stitch) >= 3:
            x, y, command = stitch[0], stitch[1], stitch[2]
            
            # Count command types
            if command == pyembroidery.STITCH:
                stats['stitch_commands']['Normal Stitch'] = stats['stitch_commands'].get('Normal Stitch', 0) + 1
            elif command == pyembroidery.JUMP:
                stats['jump_count'] += 1
                stats['stitch_commands']['Jump'] = stats['stitch_commands'].get('Jump', 0) + 1
            elif command == pyembroidery.COLOR_CHANGE:
                stats['color_changes'] += 1
                stats['stitch_commands']['Color Change'] = stats['stitch_commands'].get('Color Change', 0) + 1
            elif command == pyembroidery.TRIM:
                stats['trims'] += 1
                stats['stitch_commands']['Trim'] = stats['stitch_commands'].get('Trim', 0) + 1
            
            # Calculate distances
            if prev_x is not None and prev_y is not None:
                distance = ((x - prev_x) ** 2 + (y - prev_y) ** 2) ** 0.5
                
                if command == pyembroidery.JUMP:
                    jump_distances.append(distance)
                    stats['max_jump_distance'] = max(stats['max_jump_distance'], distance)
                elif command == pyembroidery.STITCH:
                    stitch_distances.append(distance)
                    stats['total_thread_length'] += distance
            
            prev_x, prev_y = x, y
    
    # Calculate averages
    if stitch_distances:
        stats['avg_stitch_length'] = round(sum(stitch_distances) / len(stitch_distances) / 10, 2)  # Convert to mm
    
    # Convert thread length to mm and then to more readable units
    stats['total_thread_length'] = round(stats['total_thread_length'] / 10, 2)  # mm
    if stats['total_thread_length'] > 1000:
        stats['total_thread_length_m'] = round(stats['total_thread_length'] / 1000, 2)
    
    # Convert max jump distance to mm
    stats['max_jump_distance'] = round(stats['max_jump_distance'] / 10, 2)
    
    return stats

def analyze_technical_specs(pattern, dimensions):
    """Analyze technical specifications"""
    tech_info = {
        'file_format': getattr(pattern, 'format', 'Unknown'),
        'metadata': {},
        'software_info': {},
        'creation_date': None,
        'machine_info': {},
        'pattern_complexity': 'Unknown'
    }
    
    # Extract metadata if available
    if hasattr(pattern, 'extras') and pattern.extras:
        for key, value in pattern.extras.items():
            if 'author' in key.lower():
                tech_info['metadata']['author'] = value
            elif 'title' in key.lower():
                tech_info['metadata']['title'] = value
            elif 'created' in key.lower() or 'date' in key.lower():
                tech_info['creation_date'] = value
            elif 'software' in key.lower() or 'program' in key.lower():
                tech_info['software_info']['name'] = value
            elif 'version' in key.lower():
                tech_info['software_info']['version'] = value
            elif 'machine' in key.lower():
                tech_info['machine_info']['type'] = value
            elif 'hoop' in key.lower():
                tech_info['machine_info']['hoop_size'] = value
    
    # Analyze pattern complexity
    if len(pattern.stitches) > 0:
        stitch_count = len(pattern.stitches)
        color_count = len(pattern.threadlist)
        
        if stitch_count < 1000 and color_count <= 2:
            tech_info['pattern_complexity'] = 'Proste (Simple)'
        elif stitch_count < 5000 and color_count <= 5:
            tech_info['pattern_complexity'] = 'Średnie (Medium)'
        elif stitch_count < 15000 and color_count <= 10:
            tech_info['pattern_complexity'] = 'Złożone (Complex)'
        else:
            tech_info['pattern_complexity'] = 'Bardzo złożone (Very Complex)'
    
    return tech_info

def calculate_performance_metrics(pattern, dimensions):
    """Calculate performance and time metrics"""
    metrics = {
        'estimated_time': {},
        'stitch_density': 0,
        'thread_efficiency': 0,
        'color_efficiency': 0,
        'recommended_speed': 'Unknown'
    }
    
    if len(pattern.stitches) == 0 or not dimensions:
        return metrics
    
    stitch_count = len(pattern.stitches)
    area = dimensions['width'] * dimensions['height']  # mm²
    
    # Calculate stitch density (stitches per cm²)
    if area > 0:
        metrics['stitch_density'] = round(stitch_count / (area / 100), 1)  # Convert mm² to cm²
    
    # Estimate embroidery time (rough calculation)
    # Average machine speed: 400-800 stitches per minute
    # Factor in color changes, trims, and jumps
    base_time_minutes = stitch_count / 600  # Conservative estimate
    
    # Add time for color changes and trims
    color_changes = sum(1 for stitch in pattern.stitches if len(stitch) >= 3 and stitch[2] == pyembroidery.COLOR_CHANGE)
    trims = sum(1 for stitch in pattern.stitches if len(stitch) >= 3 and stitch[2] == pyembroidery.TRIM)
    
    # Each color change adds ~30 seconds, each trim adds ~10 seconds
    additional_time = (color_changes * 0.5) + (trims * 0.17)
    
    total_time_minutes = base_time_minutes + additional_time
    
    if total_time_minutes < 60:
        metrics['estimated_time']['total'] = f"{round(total_time_minutes)} minut"
    else:
        hours = int(total_time_minutes // 60)
        minutes = int(total_time_minutes % 60)
        metrics['estimated_time']['total'] = f"{hours}h {minutes}min"
    
    metrics['estimated_time']['stitching'] = f"{round(base_time_minutes)} minut"
    metrics['estimated_time']['setup'] = f"{round(additional_time * 60)} sekund"
    
    # Thread efficiency (lower jump-to-stitch ratio is better)
    jumps = sum(1 for stitch in pattern.stitches if len(stitch) >= 3 and stitch[2] == pyembroidery.JUMP)
    if stitch_count > 0:
        metrics['thread_efficiency'] = round((1 - jumps / stitch_count) * 100, 1)
    
    # Color efficiency (fewer color changes relative to colors used is better)
    color_count = len(pattern.threadlist)
    if color_count > 0:
        metrics['color_efficiency'] = round(max(0, 100 - (color_changes / color_count) * 10), 1)
    
    # Recommended speed based on complexity
    if metrics['stitch_density'] > 8:
        metrics['recommended_speed'] = 'Wolno (400-500 ściegów/min)'
    elif metrics['stitch_density'] > 4:
        metrics['recommended_speed'] = 'Średnio (500-650 ściegów/min)'
    else:
        metrics['recommended_speed'] = 'Szybko (650-800 ściegów/min)'
    
    return metrics

def convert_pxf_to_dst(pxf_file_path):
    """Convert PXF file to DST format for detailed analysis"""
    try:
        # Create temporary DST file
        dst_file_path = pxf_file_path.replace('.pxf', '_converted.dst')
        
        # Try to read and convert the PXF file
        pattern = pyembroidery.read(pxf_file_path)
        
        if pattern is not None and len(pattern.stitches) > 0:
            # Write as DST file
            pyembroidery.write_dst(pattern, dst_file_path)
            logging.info(f"Successfully converted PXF to DST: {dst_file_path}")
            return dst_file_path
        else:
            logging.warning("PXF file has no stitch data to convert")
            return None
            
    except Exception as e:
        logging.error(f"Error converting PXF to DST: {e}")
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
            # For PXF files that failed to read, try conversion first
            logging.info("Attempting PXF to DST conversion for detailed analysis")
            dst_file = convert_pxf_to_dst(file_path)
            
            if dst_file and os.path.exists(dst_file):
                # Try to analyze the converted DST file
                pattern = pyembroidery.read(dst_file)
                if pattern is not None:
                    logging.info("Successfully converted and analyzed PXF file")
                    # Mark that this was converted for the template
                    pattern.converted_from_pxf = True
                    # Clean up the temporary DST file
                    try:
                        os.unlink(dst_file)
                    except:
                        pass
                else:
                    # Clean up failed conversion
                    try:
                        os.unlink(dst_file)
                    except:
                        pass
            
            # If conversion failed, try basic analysis
            if pattern is None:
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
            'dimensions': None,
            'converted_from_pxf': getattr(pattern, 'converted_from_pxf', False),
            'detailed_stats': {},
            'technical_info': {},
            'performance_metrics': {}
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
        
        # Detailed stitch analysis
        stitch_stats = analyze_stitch_details(pattern)
        analysis['detailed_stats'] = stitch_stats
        
        # Technical information
        tech_info = analyze_technical_specs(pattern, analysis['dimensions'])
        analysis['technical_info'] = tech_info
        
        # Performance metrics
        performance = calculate_performance_metrics(pattern, analysis['dimensions'])
        analysis['performance_metrics'] = performance
        
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
