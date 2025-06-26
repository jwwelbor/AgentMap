import React from 'react';
import styles from './DownloadButton.module.css';

interface DownloadButtonProps {
  filename: string;
  content: string;
  children: React.ReactNode;
  isZip?: boolean;
}

const DownloadButton: React.FC<DownloadButtonProps> = ({ 
  filename, 
  content, 
  children, 
  isZip = false 
}) => {
  const handleDownload = () => {
    if (isZip || content === "ZIP_PLACEHOLDER") {
      // For ZIP files, show a message instead of trying to create actual ZIP
      alert(`📦 ${filename} would be downloaded in a real implementation. This is a demo environment.`);
      return;
    }

    try {
      // Create blob and download
      const blob = new Blob([content], { type: 'text/plain' });
      const url = URL.createObjectURL(blob);
      
      // Create temporary link and trigger download
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      
      // Cleanup
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Download failed:', error);
      alert('Download failed. Please try again.');
    }
  };

  return (
    <button 
      className={styles.downloadButton}
      onClick={handleDownload}
      type="button"
      aria-label={`Download ${filename}`}
    >
      {children}
    </button>
  );
};

export default DownloadButton;
