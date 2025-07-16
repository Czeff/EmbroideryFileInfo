# PXF Embroidery File Analyzer

## Overview

This is a Flask-based web application that allows users to upload and analyze embroidery files in multiple formats (.pxf, .dst, .pes, .jef, .exp, .vp3, .hus, .xxx). The application extracts comprehensive technical information about embroidery patterns including stitch counts, thread colors, pattern dimensions, performance metrics, time estimates, and detailed technical specifications using the pyembroidery library. 

**Recent Enhancement (July 2025):** Added advanced technical analysis capabilities including:
- Detailed stitch analysis (jump distances, thread efficiency, color changes)
- Performance metrics (stitch density, estimated embroidery time)
- Technical specifications (pattern complexity, software information)
- Enhanced PXF file analysis with binary pattern recognition
- **Alternative Analysis Methods (July 15, 2025):** Implemented multiple fallback analysis methods for PXF files including:
  - XML/structured content parsing
  - Key-value pair extraction
  - Binary pattern recognition for float values
  - String pattern analysis for embroidery terms
  - Coordinate pattern analysis for stitch data
  - File structure analysis for PMLPXF headers
- **Advanced PXF Analyzer (July 15, 2025):** Created dedicated PXF analysis engine with:
  - Specialized PMLPXF header parsing
  - Section-based file structure analysis
  - Machine settings extraction (speed, tension, hoop size)
  - Technical specifications calculation
  - Comprehensive coordinate pattern analysis
  - Color section extraction with RGB values
  - Format identification and version detection
- **Inkstitch Terminology & Units Update (July 15, 2025):** Updated parameter names and units for better compatibility:
  - Changed from mm to cm for all dimension displays
  - Updated parameter names to match Inkstitch terminology (e.g., row_spacing, fill_angle, auto_underlay)
  - Translated machine settings to Polish (machine_speed, thread_tension, hoop_dimensions)
  - Enhanced fill type detection (Satyna, Zygzak, Krzyżyk, Tatami)
  - Updated thread consumption calculations in cm and meters
  - **Multi-Pattern Detection (July 15, 2025):** Enhanced to handle files with multiple embroidery patterns:
    - Detects pattern end markers (0x8003, 0x8013, 0x8023, 0x8033)
    - Analyzes jump distances between stitches to identify pattern boundaries
    - Clustering algorithm for pattern separation
    - Individual analysis for each detected pattern with dimensions and stitch counts
    - Warning system for unusual dimensions (very large or very small patterns)
    - Combined total dimensions display for multi-pattern files
    - **Per-Pattern Analysis (July 15, 2025):** Added detailed analysis for each pattern in multi-pattern files:
      - Individual stitch type analysis (running, jump, special commands)
      - Stitch density calculation (stitches per mm²) with quality assessment
      - Estimated embroidery time per pattern
      - Command distribution analysis (normal stitches vs jumps vs special commands)
      - Enhanced parameter extraction showing value ranges for multi-pattern files
      - Smart parameter aggregation (single values vs ranges for different patterns)
    - **Enhanced Performance & Resource Allocation (July 15, 2025):** Major optimizations for large files:
      - Increased timeout from 120 to 300 seconds (5 minutes) for complex files
      - Increased coordinate analysis limit from 5,000 to 15,000 points
      - Byte-by-byte analysis instead of 2-byte jumps for better accuracy
      - Increased file size limit from 16MB to 64MB
      - Added comprehensive parameter detection (stitch_length, machine_speed, auto_underlay)
      - Enhanced pattern detection sensitivity (3-point minimum instead of 5/10)
      - Extended stitch analysis from 500 to 1,500 coordinate points
      - Additional parameter categories for thorough embroidery analysis
    - **Maximum Resource Allocation Update (July 16, 2025):** Ultra-precision enhancements:
      - Extended timeout to 600 seconds (10 minutes) for maximum analysis depth
      - Increased file size limit to 128MB for industrial embroidery files
      - Expanded coordinate analysis to 30,000 points for ultra-detailed patterns
      - Enhanced stitch analysis to 3,000 coordinate points
      - Ultra-sensitive pattern detection (2-point minimum for maximum sensitivity)
      - Extended parameter chunk analysis from 32 to 64 bytes
      - Added advanced parameters: thread weight, needle size, fabric type, hoop size, stabilizer type
      - Improved clustering algorithms with 5cm distance threshold and 5-point analysis window
    - **Complete Pattern Detection Algorithm (July 16, 2025):** Advanced pattern recognition:
      - Implemented detection of complete embroidery patterns instead of individual objects
      - Added spatial analysis for grouping objects into full patterns (4cm separation threshold)
      - Enhanced embroidery sequence detection with start-fill-finish analysis
      - Pattern structure analysis based on stitch density and concentration
      - Multi-method approach: spatial grouping, command sequence, and density analysis
      - Minimum pattern size increased to 60-100 stitches for complete patterns
      - Smart pattern selection prioritizing complete patterns over fragments

Note: Some .pxf variants (like PMLPXF format) may not be fully supported by pyembroidery and users are advised to convert such files to more compatible formats like .dst, .pes, or .jef.

## User Preferences

Preferred communication style: Simple, everyday language.
Preferred language: Polish (user communicates in Polish)

## System Architecture

### Frontend Architecture
- **Framework**: Traditional server-side rendered Flask application with Jinja2 templates
- **Styling**: Bootstrap 5 with dark theme and Font Awesome icons
- **UI Pattern**: Multi-page application with form-based file upload
- **Responsive Design**: Mobile-first approach using Bootstrap's grid system

### Backend Architecture
- **Framework**: Flask (Python web framework)
- **File Processing**: pyembroidery library for reading and analyzing embroidery files
- **File Handling**: Temporary file storage using Python's tempfile module
- **Session Management**: Flask's built-in session handling with configurable secret key

### Data Processing
- **File Analysis Engine**: Uses pyembroidery to parse .pxf files and extract:
  - Stitch count and types
  - Thread colors and metadata
  - Pattern dimensions
  - Layer information
- **File Validation**: Restricts uploads to .pxf files with size limit of 16MB

## Key Components

### Core Application Files
- **app.py**: Main Flask application with route handlers and file processing logic
- **main.py**: Application entry point for running the development server
- **templates/**: HTML templates for the web interface
  - `index.html`: File upload form and landing page
  - `results.html`: Analysis results display page
- **static/style.css**: Custom CSS styling complementing Bootstrap

### File Processing Pipeline
1. **Upload Validation**: Checks file extension and size limits
2. **Secure File Handling**: Uses werkzeug's secure_filename for safe file operations
3. **Analysis Engine**: Processes embroidery files using pyembroidery library
4. **Result Presentation**: Formats analysis data for web display

### Security Features
- **File Type Restriction**: Only allows .pxf file uploads
- **File Size Limits**: 16MB maximum upload size
- **Secure Filename Handling**: Prevents directory traversal attacks
- **Temporary File Storage**: Files stored in system temp directory

## Data Flow

1. **User Upload**: User selects .pxf file through web interface
2. **File Validation**: Application validates file type and size
3. **Secure Storage**: File saved to temporary directory with secure filename
4. **Analysis Processing**: pyembroidery library analyzes the embroidery file
5. **Data Extraction**: System extracts stitch counts, colors, dimensions, and metadata
6. **Result Display**: Analysis results presented in formatted web interface
7. **Cleanup**: Temporary files handled by system temp directory management

## External Dependencies

### Python Packages
- **Flask**: Web framework for application structure and routing
- **pyembroidery**: Core library for reading and analyzing embroidery files
- **werkzeug**: Utilities for secure file handling

### Frontend Dependencies
- **Bootstrap 5**: CSS framework with dark theme from cdn.replit.com
- **Font Awesome 6**: Icon library for UI enhancement
- **CDN Delivery**: All frontend assets loaded from external CDNs

### System Dependencies
- **Python 3.x**: Runtime environment
- **Temporary File System**: For secure file storage during processing

## Deployment Strategy

### Development Configuration
- **Debug Mode**: Enabled for development with detailed error reporting
- **Host Binding**: Configured for 0.0.0.0 to allow external connections
- **Port**: Default Flask development server on port 5000
- **Secret Key**: Environment variable with fallback for development

### Production Considerations
- **Environment Variables**: SESSION_SECRET should be set in production
- **File Storage**: Currently uses system temp directory (suitable for temporary processing)
- **Security**: File validation and size limits provide basic security measures
- **Scalability**: Single-threaded Flask development server (would need WSGI server for production)

### File Management
- **Upload Strategy**: Temporary file storage with automatic cleanup
- **Storage Location**: System temporary directory for cross-platform compatibility
- **File Lifecycle**: Files processed immediately and rely on system temp cleanup