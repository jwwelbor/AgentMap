import React from 'react';
import MDXComponents from '@theme-original/MDXComponents';
import CSVTable from '@site/src/components/CSVTable';

export default {
  // Re-use the default mapping
  ...MDXComponents,
  // Map the "CSVTable" tag to our CSVTable component
  CSVTable,
};
