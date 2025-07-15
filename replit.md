# PXF Embroidery File Analyzer

## Overview

This is a Flask-based web application that allows users to upload and analyze .pxf embroidery files. The application extracts detailed information about embroidery patterns including stitch counts, thread colors, pattern dimensions, and other metadata using the pyembroidery library.

## User Preferences

Preferred communication style: Simple, everyday language.

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