import React, { useState, useMemo } from 'react';
import styles from './CSVTable.module.css';

interface CSVTableProps {
  /**
   * CSV content as a string
   */
  csvContent: string;
  
  /**
   * Optional title for the table
   */
  title?: string;
  
  /**
   * Additional CSS classes
   */
  className?: string;
  
  /**
   * Whether to show line numbers
   */
  showLineNumbers?: boolean;
  
  /**
   * Maximum number of rows to display (for performance)
   */
  maxRows?: number;
  
  /**
   * Custom filename for the downloaded/copied CSV
   */
  filename?: string;
  
  /**
   * Whether to validate Pydantic model syntax in Context columns
   */
  validatePydantic?: boolean;
  
  /**
   * Show validation warnings
   */
  showValidation?: boolean;
}

interface ParsedCSVData {
  headers: string[];
  rows: string[][];
  totalRows: number;
  validationIssues?: ValidationIssue[];
}

interface ValidationIssue {
  row: number;
  column: string;
  message: string;
  type: 'warning' | 'error' | 'info';
}

/**
 * Enhanced CSV parser that handles Pydantic model syntax and provides validation
 */
const parseCSV = (csvText: string, validatePydantic = false): ParsedCSVData => {
  if (!csvText || typeof csvText !== 'string') {
    return { headers: [], rows: [], totalRows: 0 };
  }

  const lines = csvText.trim().split('\n');
  if (lines.length === 0) {
    return { headers: [], rows: [], totalRows: 0 };
  }

  // Enhanced CSV line parser with better JSON/Python dict handling
  const parseLine = (line: string): string[] => {
    const result: string[] = [];
    let current = '';
    let inQuotes = false;
    let braceCount = 0;
    let i = 0;

    while (i < line.length) {
      const char = line[i];
      const nextChar = line[i + 1];
      
      if (char === '"') {
        if (inQuotes && nextChar === '"') {
          // Escaped quote ("" inside quoted field)
          current += '"';
          i += 2;
        } else {
          // Toggle quote state
          inQuotes = !inQuotes;
          i++;
        }
      } else if (!inQuotes && (char === '{' || char === '}')) {
        // Track braces outside of quotes for Python dict parsing
        if (char === '{') braceCount++;
        if (char === '}') braceCount--;
        current += char;
        i++;
      } else if (char === ',' && !inQuotes && braceCount === 0) {
        // Field separator (only when not in quotes and not inside dict)
        result.push(current.trim());
        current = '';
        i++;
      } else {
        current += char;
        i++;
      }
    }
    
    // Add the last field
    result.push(current.trim());
    
    // Clean up fields - remove surrounding quotes but preserve internal structure
    return result.map(field => {
      // If field starts and ends with quotes, remove them
      if (field.startsWith('"') && field.endsWith('"')) {
        return field.slice(1, -1).replace(/""/g, '"'); // Unescape doubled quotes
      }
      return field;
    });
  };

  try {
    const headers = parseLine(lines[0]);
    const rows = lines.slice(1)
      .filter(line => line.trim().length > 0)
      .map(line => parseLine(line));
    
    const validationIssues: ValidationIssue[] = [];
    
    // Validate Pydantic syntax if requested
    if (validatePydantic) {
      const contextColumnIndex = headers.findIndex(h => h.toLowerCase() === 'context');
      
      if (contextColumnIndex !== -1) {
        rows.forEach((row, rowIndex) => {
          const contextValue = row[contextColumnIndex] || '';
          if (contextValue.trim()) {
            // Check for Python dict syntax
            if (contextValue.includes('{') && contextValue.includes('}')) {
              // Check for common JSON patterns that should be Python dict
              if (contextValue.includes(': "') || contextValue.includes('": ')) {
                validationIssues.push({
                  row: rowIndex + 2,
                  column: 'Context',
                  message: 'JSON syntax detected. Use Python dict syntax: {\'key\': \'value\'}',
                  type: 'error'
                });
              }
              
              // Check for boolean values
              if (contextValue.includes('true') || contextValue.includes('false')) {
                validationIssues.push({
                  row: rowIndex + 2,
                  column: 'Context',
                  message: 'Use Python boolean syntax: True/False instead of true/false',
                  type: 'warning'
                });
              }
            }
          }
        });
      }
      
      // Check for required headers
      const requiredHeaders = ['graph_name', 'next_node'];
      requiredHeaders.forEach(required => {
        if (!headers.find(h => h === required)) {
          validationIssues.push({
            row: 1,
            column: required,
            message: `Required header '${required}' is missing`,
            type: 'error'
          });
        }
      });
    }
    
    return {
      headers,
      rows,
      totalRows: rows.length,
      validationIssues
    };
  } catch (error) {
    console.error('CSV parsing error:', error);
    return { 
      headers: [], 
      rows: [], 
      totalRows: 0,
      validationIssues: [{
        row: 1,
        column: 'General',
        message: `Parsing error: ${error.message}`,
        type: 'error'
      }]
    };
  }
};

/**
 * Enhanced CSVTable component with Pydantic validation and improved UX
 */
const CSVTable: React.FC<CSVTableProps> = ({
  csvContent,
  title,
  className,
  showLineNumbers = false,
  maxRows = 1000,
  filename = 'agentmap_workflow.csv',
  validatePydantic = true,
  showValidation = true
}) => {
  const [copied, setCopied] = useState(false);

  const parsedData = useMemo(() => {
    const data = parseCSV(csvContent, validatePydantic);
    
    // Limit rows for performance if needed
    if (maxRows && data.rows.length > maxRows) {
      return {
        ...data,
        rows: data.rows.slice(0, maxRows),
        totalRows: data.totalRows // Keep original count
      };
    }
    
    return data;
  }, [csvContent, maxRows, validatePydantic]);

  const isEmpty = parsedData.headers.length === 0 && parsedData.rows.length === 0;

  // Count validation issues by type
  const validationCounts = useMemo(() => {
    const issues = parsedData.validationIssues || [];
    return {
      errors: issues.filter(i => i.type === 'error').length,
      warnings: issues.filter(i => i.type === 'warning').length,
      info: issues.filter(i => i.type === 'info').length
    };
  }, [parsedData.validationIssues]);

  /**
   * Copy CSV content to clipboard
   */
  const handleCopyCSV = async () => {
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(csvContent);
      } else {
        // Fallback for older browsers or non-secure contexts
        const textArea = document.createElement('textarea');
        textArea.value = csvContent;
        textArea.style.position = 'fixed';
        textArea.style.left = '-999999px';
        textArea.style.top = '-999999px';
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        try {
          document.execCommand('copy');
        } catch (fallbackErr) {
          console.error('Fallback copy failed:', fallbackErr);
        }
        document.body.removeChild(textArea);
      }
      
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (error) {
      console.error('Failed to copy CSV:', error);
      // Still show feedback even if copy failed
      setCopied(true);
      setTimeout(() => setCopied(false), 1000);
    }
  };

  /**
   * Download CSV as file
   */
  const handleDownloadCSV = () => {
    try {
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      
      const link = document.createElement('a');
      link.href = url;
      link.download = filename.endsWith('.csv') ? filename : `${filename}.csv`;
      document.body.appendChild(link);
      link.click();
      
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Download failed:', error);
      alert('Download failed. Please try copying the CSV instead.');
    }
  };

  if (isEmpty) {
    return (
      <div className={`${styles.csvTable} ${className || ''}`}>
        {title && <h3 className={styles.tableTitle}>{title}</h3>}
        <div className={styles.emptyState}>
          <p>No CSV data provided or invalid format</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`${styles.csvTable} ${className || ''}`}>
      {title && <h3 className={styles.tableTitle}>{title}</h3>}
      
      {/* Validation Issues */}
      {showValidation && parsedData.validationIssues && parsedData.validationIssues.length > 0 && (
        <div className={styles.validationSection}>
          <div className={styles.validationHeader}>
            <span className={styles.validationTitle}>⚠️ Validation Results</span>
          </div>
          <div className={styles.validationCounts}>
            {validationCounts.errors > 0 && (
              <span className={styles.errorCount}>
                {validationCounts.errors} error{validationCounts.errors !== 1 ? 's' : ''}
              </span>
            )}
            {validationCounts.warnings > 0 && (
              <span className={styles.warningCount}>
                {validationCounts.warnings} warning{validationCounts.warnings !== 1 ? 's' : ''}
              </span>
            )}
            {validationCounts.info > 0 && (
              <span className={styles.infoCount}>
                {validationCounts.info} info
              </span>
            )}
          </div>
          
          <div className={styles.validationList}>
            {parsedData.validationIssues.slice(0, 5).map((issue, index) => (
              <div key={index} className={`${styles.validationIssue} ${styles[issue.type]}`}>
                <span className={styles.issueLocation}>
                  Row {issue.row}, {issue.column}:
                </span>
                <span className={styles.issueMessage}>{issue.message}</span>
              </div>
            ))}
            
            {parsedData.validationIssues.length > 5 && (
              <div className={styles.moreIssues}>
                ... and {parsedData.validationIssues.length - 5} more issues
              </div>
            )}
          </div>
        </div>
      )}
      
      <div className={styles.tableActions}>
        <button
          onClick={handleCopyCSV}
          className={styles.actionButton}
          type="button"
          aria-label="Copy CSV to clipboard"
        >
          {copied ? '✓ Copied!' : '📋 Copy CSV'}
        </button>
        
        <button
          onClick={handleDownloadCSV}
          className={styles.actionButton}
          type="button"
          aria-label="Download CSV file"
        >
          💾 Download CSV
        </button>
      </div>

      <div className={styles.tableContainer}>
        <div className={styles.tableWrapper}>
          <table className={styles.table}>
            <thead>
              <tr>
                {showLineNumbers && <th className={styles.lineNumberHeader}>#</th>}
                {parsedData.headers.map((header, index) => (
                  <th key={index} className={styles.headerCell}>
                    {header || `Column ${index + 1}`}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {parsedData.rows.map((row, rowIndex) => (
                <tr key={rowIndex} className={rowIndex % 2 === 0 ? styles.evenRow : styles.oddRow}>
                  {showLineNumbers && (
                    <td className={styles.lineNumberCell}>{rowIndex + 1}</td>
                  )}
                  {parsedData.headers.map((_, colIndex) => (
                    <td key={colIndex} className={styles.cell}>
                      {row[colIndex] || ''}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {maxRows && parsedData.totalRows > maxRows && (
        <div className={styles.truncationNotice}>
          <p>
            Showing {maxRows} of {parsedData.totalRows} rows. 
            Download the full CSV to see all data.
          </p>
        </div>
      )}

      <div className={styles.tableInfo}>
        <p>
          {parsedData.headers.length} columns, {parsedData.totalRows} rows
        </p>
      </div>
    </div>
  );
};

export default CSVTable;