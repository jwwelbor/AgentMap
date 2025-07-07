import { useState, useEffect } from 'react';
import useBaseUrl from '@docusaurus/useBaseUrl';

interface UseDownloadContentOptions {
  contentPath?: string;
  fallbackContent?: string;
}

interface UseDownloadContentReturn {
  content: string | null;
  loading: boolean;
  error: string | null;
}

/**
 * Custom hook for loading content from static files in Docusaurus
 * 
 * @param options - Configuration options
 * @param options.contentPath - Path to the static file relative to /static directory
 * @param options.fallbackContent - Fallback content to use if file loading fails
 * @returns Object containing content, loading state, and error information
 */
export const useDownloadContent = ({ 
  contentPath, 
  fallbackContent 
}: UseDownloadContentOptions = {}): UseDownloadContentReturn => {
  const [content, setContent] = useState<string | null>(fallbackContent || null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  
  // Get the properly resolved URL for the static file
  const staticFileUrl = useBaseUrl(contentPath || '');

  useEffect(() => {
    // If no contentPath is provided, use fallback content immediately
    if (!contentPath) {
      setContent(fallbackContent || null);
      setLoading(false);
      setError(null);
      return;
    }

    let isMounted = true;
    
    const loadContent = async () => {
      setLoading(true);
      setError(null);
      
      try {
        const response = await fetch(staticFileUrl);
        
        if (!response.ok) {
          throw new Error(`Failed to load content: ${response.status} ${response.statusText}`);
        }
        
        const text = await response.text();
        
        // Only update state if component is still mounted
        if (isMounted) {
          setContent(text);
          setLoading(false);
        }
      } catch (err) {
        if (isMounted) {
          const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred';
          setError(errorMessage);
          setLoading(false);
          
          // Fall back to provided fallback content if available
          if (fallbackContent) {
            setContent(fallbackContent);
            console.warn(`Failed to load content from ${contentPath}, using fallback content:`, errorMessage);
          } else {
            setContent(null);
            console.error(`Failed to load content from ${contentPath}:`, errorMessage);
          }
        }
      }
    };

    loadContent();
    
    // Cleanup function to prevent state updates on unmounted components
    return () => {
      isMounted = false;
    };
  }, [contentPath, fallbackContent, staticFileUrl]);

  return {
    content,
    loading,
    error
  };
};

export default useDownloadContent;
