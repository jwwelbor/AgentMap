import React from 'react';
import styles from './DownloadButton.module.css';
import { useDownloadContent } from '@site/src/hooks/useDownloadContent';

interface DownloadButtonProps {
  filename: string;
  content?: string;
  contentPath?: string;
  children: React.ReactNode;
  isZip?: boolean;
  lazyLoad?: boolean;
}

const DownloadButton: React.FC<DownloadButtonProps> = ({ 
  filename, 
  content, 
  contentPath,
  children, 
  isZip = false,
  lazyLoad = false
}) => {
  // Load content from static file if contentPath is provided
  const { content: fileContent, loading, error } = useDownloadContent({
    contentPath: !lazyLoad ? contentPath : undefined,
    fallbackContent: content
  });

  // Determine the final content to use
  const finalContent = fileContent || content || '';
  const isContentReady = !loading && (finalContent || error);
  const handleDownload = async () => {
    let contentToDownload = finalContent;

    // Handle lazy loading
    if (lazyLoad && contentPath && !fileContent) {
      try {
        const response = await fetch(contentPath);
        if (!response.ok) {
          throw new Error(`Failed to load content: ${response.status}`);
        }
        contentToDownload = await response.text();
      } catch (err) {
        console.error('Lazy load failed:', err);
        alert('Failed to load content for download. Please try again.');
        return;
      }
    }

    if (isZip || contentToDownload === "ZIP_PLACEHOLDER") {
      // For ZIP files, show a message instead of trying to create actual ZIP
      alert(`📦 ${filename} would be downloaded in a real implementation. This is a demo environment.`);
      return;
    }

    if (!contentToDownload) {
      alert('No content available for download.');
      return;
    }

    try {
      // Create blob and download
      const blob = new Blob([contentToDownload], { type: 'text/plain' });
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

  // Determine button state and styling
  const getButtonClass = () => {
    let className = styles.downloadButton;
    if (loading) className += ` ${styles.loading}`;
    if (error && !finalContent) className += ` ${styles.error}`;
    return className;
  };

  const getButtonContent = () => {
    if (loading) {
      return (
        <>
          <span className={styles.spinner}>⟳</span>
          Loading...
        </>
      );
    }
    if (error && !finalContent) {
      return (
        <>
          <span>⚠️</span>
          Error loading file
        </>
      );
    }
    return children;
  };

  return (
    <button 
      className={getButtonClass()}
      onClick={handleDownload}
      type="button"
      disabled={loading || (error && !finalContent)}
      aria-label={`Download ${filename}`}
      title={error && !finalContent ? `Error: ${error}` : `Download ${filename}`}
    >
      {getButtonContent()}
    </button>
  );
};

export default DownloadButton;
