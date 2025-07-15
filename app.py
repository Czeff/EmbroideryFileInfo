import os
import logging
import tempfile
from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix
import pyembroidery
from pxf_analyzer import PXFAnalyzer

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
        
        # Użyj zaawansowanego analizatora PXF
        pxf_analyzer = PXFAnalyzer(data)
        advanced_analysis = pxf_analyzer.analyze()
        
        # Konwertuj wyniki do formatu kompatybilnego z resztą aplikacji
        analysis = {
            'filename': os.path.basename(file_path),
            'file_size': len(data),
            'format_detected': advanced_analysis['file_format'].get('description', 'PXF format'),
            'stitch_count': advanced_analysis['header_analysis'].get('stitch_count', 'Unknown'),
            'thread_count': advanced_analysis['header_analysis'].get('color_count', 0),
            'colors': [],
            'stitch_types': ['Advanced PXF Analysis'],
            'layers': [],
            'dimensions': None,
            'raw_analysis': True,
            'detailed_info': {},
            'embroidery_parameters': {},
            'stitch_techniques': {},
            'machine_settings': {},
            'advanced_pxf_analysis': advanced_analysis
        }
        
        # Mapuj wyniki zaawansowanej analizy do standardowego formatu
        
        # Informacje szczegółowe
        if advanced_analysis['header_analysis']:
            header = advanced_analysis['header_analysis']
            analysis['detailed_info'] = {
                'software': advanced_analysis.get('file_format', {}).get('description', 'Unknown'),
                'format_version': advanced_analysis.get('file_format', {}).get('version', 'Unknown'),
                'header_size': header.get('header_size', 'Unknown'),
                'data_size': header.get('data_size', 'Unknown'),
                'estimated_stitches': header.get('stitch_count', 'Unknown'),
                'color_count': header.get('color_count', 0),
                'has_underlay': header.get('has_underlay', False),
                'has_applique': header.get('has_applique', False),
                'has_sequins': header.get('has_sequins', False)
            }
            
            # Wymiary z zaawansowanej analizy
            if 'dimensions' in header:
                dims = header['dimensions']
                analysis['detailed_info']['estimated_dimensions'] = f"{dims['width']:.1f} × {dims['height']:.1f} mm"
                analysis['dimensions'] = {
                    'width': dims['width'],
                    'height': dims['height'],
                    'x_offset': dims['x_offset'],
                    'y_offset': dims['y_offset']
                }
        
        # Parametry haftu
        if advanced_analysis['embroidery_parameters']:
            params = advanced_analysis['embroidery_parameters']
            analysis['embroidery_parameters'] = {
                'stitch_density': params.get('stitch_density', 'Unknown'),
                'underlay_type': params.get('underlay_type', 'Unknown'),
                'pull_compensation': params.get('pull_compensation', 'Unknown'),
                'fill_angle': params.get('fill_angle', 'Unknown'),
                'automatic_underlay': 'Enabled' if analysis['detailed_info'].get('has_underlay') else 'Unknown',
                'analysis_method': 'Advanced PXF Analysis'
            }
        
        # Ustawienia maszyny
        if advanced_analysis['machine_settings']:
            machine = advanced_analysis['machine_settings']
            analysis['machine_settings'] = {
                'speed_settings': machine.get('speed', 'Unknown'),
                'tension_settings': machine.get('tension', 'Unknown'),
                'hoop_size': machine.get('hoop_size', 'Unknown'),
                'needle_count': machine.get('needle_count', 'Unknown'),
                'machine_type': 'Unknown'
            }
        
        # Dane ściegów
        if advanced_analysis['stitch_data']:
            stitch_data = advanced_analysis['stitch_data']
            if 'dimensions' in stitch_data:
                dims = stitch_data['dimensions']
                analysis['detailed_info']['pattern_dimensions'] = f"{dims['width']:.1f} × {dims['height']:.1f} mm"
            
            if 'average_stitch_length' in stitch_data:
                analysis['detailed_info']['average_stitch_length'] = f"{stitch_data['average_stitch_length']:.1f} mm"
            
            if 'coordinate_count' in stitch_data:
                analysis['detailed_info']['coordinates_found'] = stitch_data['coordinate_count']
        
        # Specyfikacje techniczne
        if advanced_analysis['technical_specs']:
            specs = advanced_analysis['technical_specs']
            analysis['detailed_info'].update(specs)
        
        # Kolory z sekcji kolorów
        if advanced_analysis['sections_found'] and 'colors' in advanced_analysis['sections_found']:
            color_section = advanced_analysis['sections_found']['colors']
            if 'colors' in color_section:
                analysis['colors'] = []
                for color in color_section['colors']:
                    analysis['colors'].append({
                        'index': color['index'],
                        'hex': color['rgb'],
                        'brand': 'Unknown',
                        'description': f"Color {color['index'] + 1}"
                    })
                analysis['thread_count'] = len(analysis['colors'])
        
        # Jeśli analiza się powiodła, zaktualizuj informacje o typach ściegów
        if advanced_analysis['analysis_success']:
            analysis['stitch_types'] = ['PXF Advanced Analysis - Success']
            analysis['layers'] = [
                f"Format: {advanced_analysis['file_format'].get('description', 'PXF')}",
                f"Analysis: {len(advanced_analysis)} sections analyzed"
            ]
        else:
            analysis['stitch_types'] = ['PXF Advanced Analysis - Limited']
            if 'error' in advanced_analysis:
                analysis['layers'] = [f"Error: {advanced_analysis['error']}"]
        
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
                
                # Extract embroidery parameters from PXF file
                embroidery_params = extract_pxf_embroidery_parameters(data)
                analysis['embroidery_parameters'] = embroidery_params
                
                # Extract stitch techniques
                stitch_techniques = extract_pxf_stitch_techniques(data)
                analysis['stitch_techniques'] = stitch_techniques
                
                # Extract machine settings
                machine_settings = extract_pxf_machine_settings(data)
                analysis['machine_settings'] = machine_settings
                
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

def analyze_pxf_with_alternative_methods(data):
    """Try alternative methods for extracting PXF embroidery data"""
    results = {
        'method_used': [],
        'parameters_found': {},
        'raw_data_analysis': {}
    }
    
    try:
        # Method 1: File structure analysis
        if data.startswith(b'PMLPXF'):
            results['method_used'].append('PMLPXF header analysis')
            # Analyze file structure
            header_size = struct.unpack('<I', data[8:12])[0] if len(data) > 12 else 0
            if header_size > 0 and header_size < len(data):
                results['parameters_found']['header_size'] = f"{header_size} bytes"
        
        # Method 2: XML-like content search
        if b'<' in data and b'>' in data:
            results['method_used'].append('XML/structured content search')
            # Look for XML-like parameters
            import re
            xml_content = data.decode('utf-8', errors='ignore')
            
            # Search for common embroidery parameters in XML format
            xml_patterns = {
                'density': r'<density[^>]*>([^<]+)</density>',
                'underlay': r'<underlay[^>]*>([^<]+)</underlay>',
                'compensation': r'<compensation[^>]*>([^<]+)</compensation>',
                'angle': r'<angle[^>]*>([^<]+)</angle>',
                'fill': r'<fill[^>]*>([^<]+)</fill>',
                'stitch_type': r'<stitch_type[^>]*>([^<]+)</stitch_type>'
            }
            
            for param, pattern in xml_patterns.items():
                match = re.search(pattern, xml_content, re.IGNORECASE)
                if match:
                    results['parameters_found'][param] = match.group(1).strip()
        
        # Method 3: Key-value pair search
        if b'=' in data:
            results['method_used'].append('Key-value pair analysis')
            text_content = data.decode('utf-8', errors='ignore')
            
            # Search for key=value patterns
            kv_patterns = {
                'density': r'density\s*=\s*([^\s\n\r]+)',
                'underlay': r'underlay\s*=\s*([^\s\n\r]+)',
                'compensation': r'compensation\s*=\s*([^\s\n\r]+)',
                'pull_comp': r'pull_compensation\s*=\s*([^\s\n\r]+)',
                'angle': r'angle\s*=\s*([^\s\n\r]+)',
                'fill_type': r'fill_type\s*=\s*([^\s\n\r]+)',
                'stitch_length': r'stitch_length\s*=\s*([^\s\n\r]+)'
            }
            
            for param, pattern in kv_patterns.items():
                match = re.search(pattern, text_content, re.IGNORECASE)
                if match:
                    results['parameters_found'][param] = match.group(1).strip()
        
        # Method 4: Binary pattern analysis
        results['method_used'].append('Binary pattern recognition')
        
        # Look for common binary patterns that might indicate parameters
        for i in range(0, len(data) - 8, 1):
            # Check for 4-byte float values that might be parameters
            try:
                if i + 4 < len(data):
                    float_val = struct.unpack('<f', data[i:i+4])[0]
                    # Check if this could be a density value (0.1 to 10 mm)
                    if 0.1 <= float_val <= 10.0:
                        results['raw_data_analysis'][f'potential_density_{i}'] = f"{float_val:.2f}"
                    # Check if this could be an angle (-180 to 180 degrees)
                    elif -180 <= float_val <= 180:
                        results['raw_data_analysis'][f'potential_angle_{i}'] = f"{float_val:.1f}°"
                    # Check if this could be a percentage (0 to 100)
                    elif 0 <= float_val <= 100:
                        results['raw_data_analysis'][f'potential_percentage_{i}'] = f"{float_val:.1f}%"
            except:
                continue
        
        # Method 5: String pattern analysis
        results['method_used'].append('String pattern analysis')
        
        # Look for common embroidery terms in the file
        embroidery_terms = {
            'satin': 'Satin stitch detected',
            'tatami': 'Tatami fill detected',
            'zigzag': 'Zigzag pattern detected',
            'underlay': 'Underlay settings detected',
            'compensation': 'Compensation settings detected',
            'density': 'Density settings detected',
            'angle': 'Angle settings detected',
            'fill': 'Fill settings detected',
            'outline': 'Outline settings detected'
        }
        
        text_lower = data.decode('utf-8', errors='ignore').lower()
        for term, description in embroidery_terms.items():
            if term in text_lower:
                results['parameters_found'][term] = description
        
        # Method 6: Coordinate analysis for stitch patterns
        results['method_used'].append('Coordinate pattern analysis')
        
        coordinates = []
        for i in range(0, len(data) - 4, 2):
            try:
                x = struct.unpack('<h', data[i:i+2])[0]
                y = struct.unpack('<h', data[i+2:i+4])[0]
                if -32000 < x < 32000 and -32000 < y < 32000:
                    coordinates.append((x, y))
            except:
                continue
        
        if len(coordinates) > 10:
            # Analyze stitch patterns
            distances = []
            for i in range(1, min(len(coordinates), 100)):
                x1, y1 = coordinates[i-1]
                x2, y2 = coordinates[i]
                dist = ((x2-x1)**2 + (y2-y1)**2)**0.5
                distances.append(dist)
            
            if distances:
                avg_distance = sum(distances) / len(distances)
                results['parameters_found']['average_stitch_length'] = f"{avg_distance/10:.1f} mm"
                results['parameters_found']['stitch_pattern_detected'] = f"{len(coordinates)} coordinate pairs"
        
    except Exception as e:
        results['method_used'].append(f'Error in analysis: {str(e)}')
    
    return results

def extract_pxf_embroidery_parameters(data):
    """Extract embroidery parameters from PXF file using multiple analysis methods"""
    params = {
        'stitch_density': 'Unknown',
        'underlay_type': 'Unknown',
        'pull_compensation': 'Unknown',
        'push_compensation': 'Unknown',
        'stitch_angle': 'Unknown',
        'fill_pattern': 'Unknown',
        'outline_width': 'Unknown',
        'automatic_underlay': 'Unknown',
        'density_settings': {},
        'analysis_method': 'Multi-method analysis'
    }
    
    # Try alternative analysis methods
    alternative_results = analyze_pxf_with_alternative_methods(data)
    params['alternative_analysis'] = alternative_results
    
    try:
        # Method 1: Look for text-based parameters in PXF files
        text_content = data.decode('utf-8', errors='ignore')
        
        # Method 2: Hex analysis for structured data
        hex_data = data.hex()
        
        # Method 3: Try multiple density extraction methods
        density_found = False
        
        # Look for density in text content
        import re
        density_patterns = [
            r'density[:\s]*(\d+\.?\d*)',
            r'DENSITY[:\s]*(\d+\.?\d*)',
            r'stitch_density[:\s]*(\d+\.?\d*)',
            r'line_spacing[:\s]*(\d+\.?\d*)',
            r'spacing[:\s]*(\d+\.?\d*)'
        ]
        
        for pattern in density_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                density_val = float(match.group(1))
                if 0.1 <= density_val <= 50:  # Reasonable density range in mm
                    params['stitch_density'] = f"{density_val:.1f} mm"
                    density_found = True
                    break
        
        # Look for density settings in PXF files using binary search
        if not density_found:
            for i in range(0, len(data) - 16):
                chunk = data[i:i+16]
                
                # Look for density markers (common in Tajima PXF files)
                if b'DENSITY' in chunk or b'density' in chunk:
                    try:
                        # Try to extract density value from surrounding bytes
                        density_bytes = data[i+8:i+12]
                        if len(density_bytes) == 4:
                            import struct
                            density_val = struct.unpack('<I', density_bytes)[0]
                            if 10 <= density_val <= 1000:  # Reasonable density range
                                params['stitch_density'] = f"{density_val/100:.1f} mm"
                                density_found = True
                                break
                    except:
                        pass
                
                # Alternative: look for float values near density markers
                if not density_found and (b'dens' in chunk.lower() or b'spac' in chunk.lower()):
                    try:
                        # Try to find float values in nearby bytes
                        for offset in range(-20, 21, 4):
                            if i + offset >= 0 and i + offset + 4 < len(data):
                                test_bytes = data[i+offset:i+offset+4]
                                float_val = struct.unpack('<f', test_bytes)[0]
                                if 0.1 <= float_val <= 20:  # Reasonable density range
                                    params['stitch_density'] = f"{float_val:.1f} mm"
                                    density_found = True
                                    break
                    except:
                        continue
                
                if density_found:
                    break
            
            # Look for underlay settings
            if b'UNDERLAY' in chunk or b'underlay' in chunk:
                underlay_info = data[i:i+50].decode('utf-8', errors='ignore')
                if 'AUTO' in underlay_info:
                    params['automatic_underlay'] = 'Enabled'
                    params['underlay_type'] = 'Automatic'
                elif 'ZIGZAG' in underlay_info:
                    params['underlay_type'] = 'Zigzag'
                elif 'EDGE' in underlay_info:
                    params['underlay_type'] = 'Edge Run'
                elif 'CENTER' in underlay_info:
                    params['underlay_type'] = 'Center Run'
            
            # Look for pull compensation settings
            if b'PULL' in chunk or b'pull' in chunk:
                try:
                    comp_bytes = data[i+4:i+8]
                    if len(comp_bytes) >= 2:
                        comp_val = struct.unpack('<H', comp_bytes[:2])[0]
                        if 0 <= comp_val <= 100:
                            params['pull_compensation'] = f"{comp_val/10:.1f}%"
                except:
                    pass
            
            # Look for fill pattern information
            if b'FILL' in chunk or b'fill' in chunk:
                fill_info = data[i:i+30].decode('utf-8', errors='ignore')
                if 'SATIN' in fill_info:
                    params['fill_pattern'] = 'Satin'
                elif 'ZIGZAG' in fill_info:
                    params['fill_pattern'] = 'Zigzag'
                elif 'CROSS' in fill_info:
                    params['fill_pattern'] = 'Cross Hatch'
                elif 'TATAMI' in fill_info:
                    params['fill_pattern'] = 'Tatami'
        
        # Extract angle information from stitch patterns
        angle_found = False
        for i in range(0, len(data) - 8, 4):
            try:
                # Look for angle patterns in coordinate data
                if i + 8 < len(data):
                    x1 = struct.unpack('<h', data[i:i+2])[0]
                    y1 = struct.unpack('<h', data[i+2:i+4])[0]
                    x2 = struct.unpack('<h', data[i+4:i+6])[0]
                    y2 = struct.unpack('<h', data[i+6:i+8])[0]
                    
                    if all(abs(val) < 10000 for val in [x1, y1, x2, y2]):
                        # Calculate angle if we have valid coordinates
                        import math
                        if x2 != x1 and not angle_found:
                            angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
                            if -180 <= angle <= 180:
                                params['stitch_angle'] = f"{angle:.0f}°"
                                angle_found = True
                                break
            except:
                continue
                
    except Exception as e:
        logging.warning(f"Error extracting embroidery parameters: {e}")
    
    return params

def extract_pxf_stitch_techniques(data):
    """Extract stitch techniques from PXF file"""
    techniques = {
        'fill_techniques': [],
        'outline_techniques': [],
        'special_effects': [],
        'stitch_types_used': [],
        'density_variations': []
    }
    
    try:
        # Analyze stitch patterns to determine techniques
        stitch_patterns = []
        for i in range(0, len(data) - 12, 4):
            try:
                x = struct.unpack('<h', data[i:i+2])[0]
                y = struct.unpack('<h', data[i+2:i+4])[0]
                if abs(x) < 10000 and abs(y) < 10000:
                    stitch_patterns.append((x, y))
            except:
                continue
        
        if len(stitch_patterns) > 10:
            # Analyze patterns to determine techniques
            distances = []
            angles = []
            
            for i in range(1, min(len(stitch_patterns), 1000)):
                x1, y1 = stitch_patterns[i-1]
                x2, y2 = stitch_patterns[i]
                
                distance = math.sqrt((x2-x1)**2 + (y2-y1)**2)
                distances.append(distance)
                
                if x2 != x1:
                    angle = math.degrees(math.atan2(y2-y1, x2-x1))
                    angles.append(angle)
            
            # Determine fill techniques based on patterns
            if distances:
                avg_distance = sum(distances) / len(distances)
                distance_variance = sum((d - avg_distance)**2 for d in distances) / len(distances)
                
                if distance_variance < 100:  # Low variance = consistent spacing
                    techniques['fill_techniques'].append('Uniform Fill')
                else:
                    techniques['fill_techniques'].append('Variable Density Fill')
                
                if avg_distance < 50:  # Close stitches
                    techniques['stitch_types_used'].append('Dense Satin')
                elif avg_distance < 200:
                    techniques['stitch_types_used'].append('Normal Fill')
                else:
                    techniques['stitch_types_used'].append('Open Fill')
            
            # Analyze angles for patterns
            if angles:
                angle_changes = sum(1 for i in range(1, len(angles)) if abs(angles[i] - angles[i-1]) > 45)
                if angle_changes > len(angles) * 0.3:
                    techniques['fill_techniques'].append('Cross Hatch')
                    techniques['special_effects'].append('Multi-directional Fill')
                else:
                    techniques['fill_techniques'].append('Directional Fill')
        
        # Look for specific technique markers in the file
        technique_markers = {
            b'SATIN': 'Satin Stitch',
            b'ZIGZAG': 'Zigzag Fill',
            b'TATAMI': 'Tatami Fill',
            b'CROSS': 'Cross Hatch',
            b'OUTLINE': 'Outline Stitch',
            b'BEAN': 'Bean Stitch',
            b'STEM': 'Stem Stitch',
            b'CHAIN': 'Chain Stitch',
            b'BLANKET': 'Blanket Stitch',
            b'APPLIQUE': 'Applique',
            b'MOTIF': 'Motif Fill',
            b'RADIAL': 'Radial Fill',
            b'SPIRAL': 'Spiral Fill',
            b'CONTOUR': 'Contour Fill'
        }
        
        for marker, technique in technique_markers.items():
            if marker in data:
                if 'FILL' in marker.decode() or 'TATAMI' in marker.decode():
                    techniques['fill_techniques'].append(technique)
                elif 'OUTLINE' in marker.decode() or 'STEM' in marker.decode():
                    techniques['outline_techniques'].append(technique)
                else:
                    techniques['special_effects'].append(technique)
        
        # Remove duplicates
        for key in techniques:
            if isinstance(techniques[key], list):
                techniques[key] = list(set(techniques[key]))
                
    except Exception as e:
        logging.warning(f"Error extracting stitch techniques: {e}")
    
    return techniques

def extract_pxf_machine_settings(data):
    """Extract machine settings from PXF file"""
    settings = {
        'speed_settings': 'Unknown',
        'tension_settings': 'Unknown',
        'needle_settings': 'Unknown',
        'hoop_size': 'Unknown',
        'machine_type': 'Unknown',
        'thread_trimming': 'Unknown',
        'color_sequence': 'Unknown',
        'jump_settings': {}
    }
    
    try:
        # Look for machine-specific settings
        for i in range(0, len(data) - 32):
            chunk = data[i:i+32]
            
            # Look for speed settings
            if b'SPEED' in chunk or b'speed' in chunk:
                try:
                    speed_bytes = data[i+8:i+12]
                    if len(speed_bytes) >= 2:
                        speed = struct.unpack('<H', speed_bytes[:2])[0]
                        if 100 <= speed <= 2000:  # Reasonable speed range
                            settings['speed_settings'] = f"{speed} stitches/min"
                except:
                    pass
            
            # Look for tension settings
            if b'TENSION' in chunk or b'tension' in chunk:
                try:
                    tension_bytes = data[i+8:i+12]
                    if len(tension_bytes) >= 2:
                        tension = struct.unpack('<H', tension_bytes[:2])[0]
                        if 1 <= tension <= 100:
                            settings['tension_settings'] = f"Level {tension}"
                except:
                    pass
            
            # Look for hoop size information
            if b'HOOP' in chunk or b'hoop' in chunk:
                hoop_info = data[i:i+50].decode('utf-8', errors='ignore')
                hoop_sizes = ['100x100', '130x180', '150x240', '200x300', '360x200']
                for size in hoop_sizes:
                    if size in hoop_info:
                        settings['hoop_size'] = f"{size} mm"
                        break
            
            # Look for machine type
            if b'TAJIMA' in chunk:
                settings['machine_type'] = 'Tajima'
            elif b'BROTHER' in chunk:
                settings['machine_type'] = 'Brother'
            elif b'BERNINA' in chunk:
                settings['machine_type'] = 'Bernina'
            elif b'HUSQVARNA' in chunk:
                settings['machine_type'] = 'Husqvarna Viking'
            elif b'JANOME' in chunk:
                settings['machine_type'] = 'Janome'
            elif b'PFAFF' in chunk:
                settings['machine_type'] = 'Pfaff'
            
            # Look for trimming settings
            if b'TRIM' in chunk or b'trim' in chunk:
                trim_info = data[i:i+30].decode('utf-8', errors='ignore')
                if 'AUTO' in trim_info:
                    settings['thread_trimming'] = 'Automatic'
                elif 'MANUAL' in trim_info:
                    settings['thread_trimming'] = 'Manual'
        
        # Analyze jump settings
        jump_distances = []
        for i in range(0, len(data) - 8, 4):
            try:
                x1 = struct.unpack('<h', data[i:i+2])[0]
                y1 = struct.unpack('<h', data[i+2:i+4])[0]
                x2 = struct.unpack('<h', data[i+4:i+6])[0]
                y2 = struct.unpack('<h', data[i+6:i+8])[0]
                
                if all(abs(val) < 10000 for val in [x1, y1, x2, y2]):
                    distance = math.sqrt((x2-x1)**2 + (y2-y1)**2)
                    if distance > 500:  # Likely a jump
                        jump_distances.append(distance)
            except:
                continue
        
        if jump_distances:
            avg_jump = sum(jump_distances) / len(jump_distances)
            max_jump = max(jump_distances)
            settings['jump_settings'] = {
                'average_jump': f"{avg_jump/10:.1f} mm",
                'max_jump': f"{max_jump/10:.1f} mm",
                'jump_count': len(jump_distances)
            }
            
    except Exception as e:
        logging.warning(f"Error extracting machine settings: {e}")
    
    return settings

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
