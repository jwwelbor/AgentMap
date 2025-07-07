---
---

# Download Content System Guide

This guide explains the new file-based content system for downloadable files in the AgentMap documentation, replacing the previous inline content approach.

## Overview

The AgentMap documentation now uses a static file-based system for downloadable content, which provides several benefits:

- **Cleaner MDX files**: No more complex character escaping for embedded content
- **Better maintainability**: Content files are separate from documentation structure
- **Improved performance**: Content can be loaded on-demand (lazy loading)
- **Version control friendly**: Easier to track changes to individual files
- **Backward compatibility**: Existing inline content continues to work

## File Organization

All downloadable content is organized under `/static/downloads/` with the following structure:

```
static/downloads/
├── README.md                    # Documentation for file organization
├── lessons/                     # Tutorial lesson content
│   ├── lesson3/                # Lesson 3: Building Your First Multi-Agent System
│   └── lesson7/                # Lesson 7: Advanced Agent Orchestration
├── templates/                   # Workflow templates and configurations
│   ├── basic_workflow_template.csv
│   ├── customer_support_template.csv
│   ├── data_processing_template.csv
│   └── weather_bot_template.csv
└── examples/                    # Code examples and reference implementations
```

### Naming Conventions

- **Lessons**: Use descriptive filenames with underscores: `agent_configuration.yaml`, `workflow_example.py`
- **Templates**: Follow pattern `{use_case}_template.{extension}`
- **Examples**: Follow pattern `{feature}_{type}_example.{extension}`
- **General**: Use lowercase, underscores for separation, descriptive names

## Using the DownloadButton Component

The enhanced `DownloadButton` component supports both traditional inline content and the new file-based approach.

### File-Based Content (Recommended)

```jsx
import DownloadButton from '@site/src/components/DownloadButton';

// Basic usage with static file
<DownloadButton 
  filename=\"workflow_config.yaml\" 
  contentPath=\"/downloads/examples/workflow_config_example.yaml\"
>
  📄 Download Workflow Configuration
</DownloadButton>

// With lazy loading for large files
<DownloadButton 
  filename=\"large_dataset.csv\" 
  contentPath=\"/downloads/examples/large_dataset_example.csv\"
  lazyLoad={true}
>
  📊 Download Large Dataset
</DownloadButton>
```

### Backward Compatibility (Legacy Support)

```jsx
// Existing inline content continues to work
<DownloadButton 
  filename=\"simple_config.yaml\" 
  content={`
name: simple_agent
type: assistant
model: gpt-4
`}
>
  📄 Download Configuration
</DownloadButton>
```

### Hybrid Approach (Fallback Support)

```jsx
// File-based with inline fallback
<DownloadButton 
  filename=\"config.yaml\" 
  contentPath=\"/downloads/examples/config_example.yaml\"
  content={`# Fallback content if file fails to load
name: fallback_agent
type: assistant`}
>
  📄 Download Configuration
</DownloadButton>
```

## Component Props Reference

| Prop | Type | Required | Description |
|------|------|----------|-------------|
| `filename` | `string` | ✅ | Name for the downloaded file |
| `children` | `ReactNode` | ✅ | Button content/text |
| `content` | `string` | ❌ | Inline content (legacy support) |
| `contentPath` | `string` | ❌ | Path to static file relative to `/static` |
| `isZip` | `boolean` | ❌ | Whether content is a ZIP file (shows demo message) |
| `lazyLoad` | `boolean` | ❌ | Load content only when download is clicked |

## Loading States and Error Handling

The component automatically handles loading and error states:

- **Loading**: Shows spinner animation and \"Loading...\" text
- **Error**: Shows warning icon and error message, falls back to inline content if available
- **Success**: Normal button appearance and functionality

## Migration Guide

### Step 1: Assess Current Content

Review your MDX files and identify `DownloadButton` components with inline content:

```jsx
// Find patterns like this
<DownloadButton filename="example.txt" content={`...long content...`}>
```

### Step 2: Extract Content to Static Files

1. Create appropriate file in `/static/downloads/` structure
2. Copy the inline content to the new file
3. Ensure proper file encoding (UTF-8 for text files)

### Step 3: Update Component Usage

Replace inline content with file path:

```jsx
// Before
<DownloadButton 
  filename=\"agent_config.yaml\" 
  content={`name: example_agent
type: assistant
model: gpt-4
capabilities:
  - text_processing
  - file_handling`}
>
  Download Configuration
</DownloadButton>

// After
<DownloadButton 
  filename=\"agent_config.yaml\" 
  contentPath=\"/downloads/lessons/lesson3/agent_config.yaml\"
>
  Download Configuration
</DownloadButton>
```

### Step 4: Test and Verify

1. Start the development server: `npm start`
2. Navigate to the updated page
3. Test the download functionality
4. Verify the file downloads correctly with expected content

## Migration Checklist

- [ ] Identify all `DownloadButton` components with inline content
- [ ] Create appropriate directory structure in `/static/downloads/`
- [ ] Extract content to individual files with proper naming
- [ ] Update component props to use `contentPath`
- [ ] Test download functionality in development
- [ ] Verify file encoding and content accuracy
- [ ] Update any related documentation or examples
- [ ] Consider enabling `lazyLoad` for large files (>100KB)

## Best Practices

### File Management
- Keep individual files under 5MB for optimal performance
- Use UTF-8 encoding for text files
- Organize files logically in subdirectories
- Use descriptive, consistent naming conventions

### Performance
- Enable `lazyLoad` for files larger than 100KB
- Consider splitting very large files into smaller chunks
- Use appropriate file formats (CSV for data, YAML for configs, etc.)

### Content Quality
- Validate file content before committing
- Include comments or headers in configuration files
- Ensure examples are functional and up-to-date
- Test downloaded files in their intended use context

### Documentation
- Update file paths when reorganizing content
- Document any special requirements or dependencies
- Include version information in file headers when relevant

## Troubleshooting

### Common Issues

**Download button shows \"Error loading file\"**
- Verify the file exists at the specified path
- Check file permissions and encoding
- Ensure the path starts with `/downloads/`
- Test the URL directly: `http://localhost:3000/downloads/path/to/file`

**Content appears corrupted or malformed**
- Verify file encoding is UTF-8
- Check for special characters that need escaping
- Ensure line endings are consistent (LF recommended)

**Button appears stuck in loading state**
- Check browser console for network errors
- Verify Docusaurus development server is running
- Clear browser cache and restart development server

**Download fails with \"No content available\"**
- Ensure either `content` or `contentPath` is provided
- Check that the file isn't empty
- Verify component props are correctly passed

### Development Tips

1. **Test Locally**: Always test downloads in development before deploying
2. **Use Browser DevTools**: Check Network tab for failed requests
3. **Validate Paths**: Ensure static file paths are correct and accessible
4. **Content Preview**: Use `curl` or direct browser access to verify file content

## Related Components

This file-based system can be extended to other components that handle downloadable content:

- **TemplateLibrary**: Uses similar patterns for CSV template files
- **CodeExamples**: Can leverage the same file organization for code samples
- **ConfigurationGuides**: Benefits from external configuration files

## Future Enhancements

Planned improvements to the download content system:

- **Automatic file validation**: Lint checks for common file format issues
- **Content versioning**: Support for multiple versions of template files
- **Batch downloads**: ZIP file generation for multiple related files
- **Preview functionality**: In-browser preview before download
- **Search integration**: Make downloadable content searchable

---

For questions or issues with the download content system, please refer to the [static/downloads/README.md](../../static/downloads/README.md) or create an issue in the project repository.
