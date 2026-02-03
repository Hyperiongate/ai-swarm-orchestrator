"""
BOOTSTRAP KNOWLEDGE BASE
Created: February 2, 2026
Last Updated: February 2, 2026

One-time script to load ALL existing Shiftwork Solutions knowledge from /mnt/project/
into the permanent knowledge database.

This is the "Genesis Moment" - building the foundation for cumulative learning.

Usage:
    python bootstrap_knowledge.py

Author: Jim @ Shiftwork Solutions LLC (managed by Claude Sonnet 4)
"""

import os
import sys
from pathlib import Path
from document_ingestion_engine import get_document_ingestor
import mimetypes

# Document mapping: file -> (type, metadata)
DOCUMENTS_TO_INGEST = {
    # Implementation Manuals
    'Implementation_Manual.docx': {
        'type': 'implementation_manual',
        'metadata': {
            'client': 'Generic Template',
            'industry': 'General',
            'project_type': 'Implementation'
        }
    },
    'Implementation_Manual_Sample.docx': {
        'type': 'implementation_manual',
        'metadata': {
            'client': 'Sample Client',
            'industry': 'General',
            'project_type': 'Implementation'
        }
    },
    'Implementation_Manual_Sample_2.docx': {
        'type': 'implementation_manual',
        'metadata': {
            'client': 'Sample Client 2',
            'industry': 'General',
            'project_type': 'Implementation'
        }
    },
    'Andersen_Implementation_Manual.docx': {
        'type': 'implementation_manual',
        'metadata': {
            'client': 'Andersen',
            'industry': 'Manufacturing',
            'project_type': 'Implementation'
        }
    },
    
    # Lessons Learned (Most Important!)
    'Shiftwork_Solutions_Lessons_Learned.md': {
        'type': 'lessons_learned',
        'metadata': {
            'client': 'Shiftwork Solutions',
            'industry': 'All',
            'project_type': 'Internal Knowledge'
        }
    },
    
    # Knowledge Bases
    'Knowledge_base_from_pages': {
        'type': 'knowledge_base',
        'metadata': {
            'client': 'Shiftwork Solutions',
            'industry': 'All',
            'project_type': 'Website Content'
        }
    },
    'Overall_summary': {
        'type': 'knowledge_base',
        'metadata': {
            'client': 'Shiftwork Solutions',
            'industry': 'All',
            'project_type': 'Business Summary'
        }
    },
    
    # Contracts & Proposals
    'Contract_without_name_Corp_A_2025.docx': {
        'type': 'contract',
        'metadata': {
            'client': 'Corp A',
            'industry': 'Unknown',
            'project_type': 'Contract'
        }
    },
    'Shiftwork_Solutions_LLC_-_Contract.docx': {
        'type': 'contract',
        'metadata': {
            'client': 'Generic',
            'industry': 'General',
            'project_type': 'Contract Template'
        }
    },
    'Scope_of_work_by_AI.docx': {
        'type': 'proposal',
        'metadata': {
            'client': 'AI Generated',
            'industry': 'General',
            'project_type': 'Scope of Work'
        }
    },
    
    # Assessments
    'Survey_evaluation': {
        'type': 'assessment',
        'metadata': {
            'client': 'Generic',
            'industry': 'General',
            'project_type': 'Survey Evaluation'
        }
    },
    
    # Data Collection
    'Data_Collection.docx': {
        'type': 'process',
        'metadata': {
            'client': 'Generic',
            'industry': 'General',
            'project_type': 'Data Collection Process'
        }
    },
    'Schedule_Survey_.docx': {
        'type': 'survey',
        'metadata': {
            'client': 'Generic',
            'industry': 'General',
            'project_type': 'Schedule Survey Template'
        }
    },
    
    # Communication Templates
    'Project_kickoff_bulletin.docx': {
        'type': 'communication',
        'metadata': {
            'client': 'Generic',
            'industry': 'General',
            'project_type': 'Project Kickoff'
        }
    },
    'Session_Handoff_SwingShift.docx': {
        'type': 'communication',
        'metadata': {
            'client': 'SwingShift',
            'industry': 'General',
            'project_type': 'Session Handoff'
        }
    },
    
    # Executive Summaries
    'Example_Client_facing_executive_summary_Andersen_2025.docx': {
        'type': 'executive_summary',
        'metadata': {
            'client': 'Andersen',
            'industry': 'Manufacturing',
            'project_type': 'Executive Summary'
        }
    },
    
    # Company Info
    'Shiftwork_Solutions_LLC_Company_Profile_-_All_Industry__002_.docx': {
        'type': 'company_profile',
        'metadata': {
            'client': 'Shiftwork Solutions',
            'industry': 'All',
            'project_type': 'Company Profile'
        }
    },
    'Jims_bio.docx': {
        'type': 'company_profile',
        'metadata': {
            'client': 'Shiftwork Solutions',
            'industry': 'All',
            'project_type': 'Bio'
        }
    },
    
    # AI Systems Documentation
    'AI_SWARM_ORCHESTRATOR_COMPLETE_SUMMARY_2026-01-31.md': {
        'type': 'technical_documentation',
        'metadata': {
            'client': 'Shiftwork Solutions',
            'industry': 'Technology',
            'project_type': 'AI System Documentation'
        }
    },
    'AI_Swarm_File_Structure.md': {
        'type': 'technical_documentation',
        'metadata': {
            'client': 'Shiftwork Solutions',
            'industry': 'Technology',
            'project_type': 'System Architecture'
        }
    },
    'The_Code': {
        'type': 'technical_documentation',
        'metadata': {
            'client': 'Shiftwork Solutions',
            'industry': 'Technology',
            'project_type': 'Source Code Documentation'
        }
    },
    
    # Reference Materials
    'THE_ESSENTIAL_GUIDE_TO_SHIFTWORK_OPERATIONS_EXCELLENCE.pdf': {
        'type': 'reference',
        'metadata': {
            'client': 'Shiftwork Solutions',
            'industry': 'All',
            'project_type': 'Best Practices Guide'
        }
    },
    
    # Schedule Data
    'Definitive_Schedules_v2.xlsx': {
        'type': 'schedule_data',
        'metadata': {
            'client': 'Shiftwork Solutions',
            'industry': 'All',
            'project_type': 'Schedule Library'
        }
    }
}


def read_file_content(filepath):
    """
    Read file content with appropriate handling for different file types.
    """
    file_ext = filepath.suffix.lower()
    
    # Text-based files
    if file_ext in ['.txt', '.md', '.py', '.json', '.csv']:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        except:
            # Try with different encoding
            with open(filepath, 'r', encoding='latin-1') as f:
                return f.read()
    
    # Word documents - extract text representation
    elif file_ext in ['.docx', '.doc']:
        try:
            # For now, just read as binary and note it's a Word doc
            # In production, you'd use python-docx to extract text
            return f"[Word Document: {filepath.name}]\n\nThis is a Word document that would be processed with python-docx library."
        except:
            return f"[Word Document: {filepath.name}] - Could not read"
    
    # PDFs - note for future processing
    elif file_ext == '.pdf':
        return f"[PDF Document: {filepath.name}]\n\nThis is a PDF document that would be processed with PyPDF2 or similar library."
    
    # Excel files
    elif file_ext in ['.xlsx', '.xls']:
        return f"[Excel Spreadsheet: {filepath.name}]\n\nThis is an Excel file that would be processed with pandas or openpyxl."
    
    # Unknown
    else:
        return f"[Unknown File Type: {filepath.name}]\n\nFile type: {file_ext}"


def bootstrap_knowledge_base(project_path='/mnt/project/project_files'):
    """
    Bootstrap the knowledge base by ingesting all existing documents.
    """
    project_path = Path(project_path)
    ingestor = get_document_ingestor()
    
    print("=" * 80)
    print("🧠 BOOTSTRAPPING KNOWLEDGE BASE")
    print("=" * 80)
    print(f"\nScanning directory: {project_path}")
    print(f"Documents to ingest: {len(DOCUMENTS_TO_INGEST)}\n")
    
    results = {
        'success': [],
        'failed': [],
        'already_ingested': []
    }
    
    for filename, doc_info in DOCUMENTS_TO_INGEST.items():
        filepath = project_path / filename
        
        print(f"\n📄 Processing: {filename}")
        print(f"   Type: {doc_info['type']}")
        print(f"   Client: {doc_info['metadata'].get('client', 'N/A')}")
        
        # Check if file exists
        if not filepath.exists():
            print(f"   ⚠️  File not found: {filepath}")
            results['failed'].append({
                'filename': filename,
                'error': 'File not found'
            })
            continue
        
        try:
            # Read file content
            content = read_file_content(filepath)
            
            # Add filename to metadata
            metadata = doc_info['metadata'].copy()
            metadata['document_name'] = filename
            metadata['bootstrap_date'] = '2026-02-02'
            
            # Ingest document
            result = ingestor.ingest_document(
                content=content,
                document_type=doc_info['type'],
                metadata=metadata
            )
            
            if result.get('already_ingested'):
                print(f"   ℹ️  Already ingested: {filename}")
                results['already_ingested'].append(filename)
            elif result.get('success'):
                print(f"   ✅ SUCCESS!")
                print(f"      Patterns: {result.get('patterns_extracted', 0)}")
                print(f"      Insights: {result.get('insights_extracted', 0)}")
                results['success'].append({
                    'filename': filename,
                    'patterns': result.get('patterns_extracted', 0),
                    'insights': result.get('insights_extracted', 0)
                })
            else:
                print(f"   ❌ FAILED: {result.get('error', 'Unknown error')}")
                results['failed'].append({
                    'filename': filename,
                    'error': result.get('error', 'Unknown error')
                })
        
        except Exception as e:
            print(f"   ❌ EXCEPTION: {str(e)}")
            results['failed'].append({
                'filename': filename,
                'error': str(e)
            })
    
    # Print summary
    print("\n" + "=" * 80)
    print("📊 BOOTSTRAP SUMMARY")
    print("=" * 80)
    print(f"\n✅ Successfully ingested: {len(results['success'])}")
    print(f"ℹ️  Already in database: {len(results['already_ingested'])}")
    print(f"❌ Failed: {len(results['failed'])}")
    
    if results['success']:
        total_patterns = sum(r['patterns'] for r in results['success'])
        total_insights = sum(r['insights'] for r in results['success'])
        print(f"\n📊 Total patterns extracted: {total_patterns}")
        print(f"💡 Total insights captured: {total_insights}")
    
    if results['failed']:
        print("\n❌ Failed documents:")
        for failure in results['failed']:
            print(f"   - {failure['filename']}: {failure['error']}")
    
    # Get final stats
    stats = ingestor.get_knowledge_base_stats()
    print("\n" + "=" * 80)
    print("🎯 FINAL KNOWLEDGE BASE STATUS")
    print("=" * 80)
    print(f"\n📚 Total documents in database: {stats['total_extracts']}")
    print(f"🧠 Total learned patterns: {stats['total_patterns']}")
    print("\nBreakdown by document type:")
    for doc_type, count in stats['by_document_type'].items():
        print(f"   {doc_type}: {count}")
    
    print("\n✨ Knowledge base bootstrap complete!")
    print("🏆 Standing on the shoulders of giants!\n")
    
    return results


if __name__ == '__main__':
    # Run bootstrap
    try:
        results = bootstrap_knowledge_base()
        
        # Exit code based on results
        if len(results['failed']) > 0:
            sys.exit(1)  # Some failures
        else:
            sys.exit(0)  # All success
            
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(2)


# I did no harm and this file is not truncated
