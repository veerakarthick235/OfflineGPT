import { useRef, useCallback } from 'react';
import { uploadAttachments, getAttachmentStatus, deleteAttachment } from '../../api/client';
import AttachmentChip from './AttachmentChip';
import './AttachmentPreview.css';

// File types accepted
const ACCEPT = [
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'text/plain', 'text/markdown', 'text/csv', 'text/html', 'text/css',
  'application/json', 'application/xml', 'text/xml',
  'image/png', 'image/jpeg', 'image/webp', 'image/bmp', 'image/gif',
  'application/zip', 'application/x-zip-compressed',
  // Code files via extension
  '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.c', '.cpp', '.h', '.cs',
  '.go', '.rs', '.rb', '.php', '.swift', '.kt', '.sql', '.sh', '.bash',
  '.yaml', '.yml', '.toml', '.ini', '.md', '.rtf',
].join(',');

const POLLING_INTERVAL = 1500; // ms

/**
 * AttachmentPreview manages the list of attached files above the textarea.
 * Props:
 *   attachments:    array of attachment objects {id, filename, file_type, status, …}
 *   setAttachments: state setter
 *   conversationId: current conversation ID (may be null for new chat)
 */
export default function AttachmentPreview({ attachments, setAttachments, conversationId }) {
  const fileInputRef = useRef();
  const pollingRefs  = useRef({}); // { [id]: intervalId }

  const _poll = useCallback((id) => {
    if (pollingRefs.current[id]) return;
    const iv = setInterval(async () => {
      try {
        const { status, error } = await getAttachmentStatus(id);
        setAttachments(prev => prev.map(a =>
          a.id === id ? { ...a, status, error_msg: error } : a
        ));
        if (status === 'ready' || status === 'error') {
          clearInterval(iv);
          delete pollingRefs.current[id];
        }
      } catch {
        clearInterval(iv);
        delete pollingRefs.current[id];
      }
    }, POLLING_INTERVAL);
    pollingRefs.current[id] = iv;
  }, [setAttachments]);

  const handleFiles = useCallback(async (fileList) => {
    const files = Array.from(fileList);
    if (!files.length) return;

    // Optimistic: add placeholder chips
    const placeholders = files.map(f => ({
      id:            `tmp_${Date.now()}_${f.name}`,
      filename:      f.name,
      original_name: f.name,
      file_type:     'unknown',
      status:        'uploading',
    }));
    setAttachments(prev => [...prev, ...placeholders]);

    try {
      const res = await uploadAttachments(files, conversationId);
      const uploaded = res.attachments || [];

      // Replace placeholders with real records
      setAttachments(prev => {
        const stillUploading = prev.filter(a => !a.id.startsWith('tmp_'));
        return [...stillUploading, ...uploaded];
      });

      // Poll processing status for each
      uploaded.forEach(att => {
        if (att.status !== 'ready') {
          _poll(att.id);
        }
      });
    } catch (err) {
      // Mark placeholders as error
      setAttachments(prev =>
        prev.map(a =>
          a.id.startsWith('tmp_') ? { ...a, status: 'error' } : a
        )
      );
    }
  }, [conversationId, setAttachments, _poll]);

  const handleInputChange = (e) => {
    handleFiles(e.target.files);
    e.target.value = ''; // allow re-selecting same file
  };

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    handleFiles(e.dataTransfer.files);
  }, [handleFiles]);

  const handleRemove = useCallback(async (id) => {
    // Remove from UI immediately
    setAttachments(prev => prev.filter(a => a.id !== id));
    // Clean up polling
    if (pollingRefs.current[id]) {
      clearInterval(pollingRefs.current[id]);
      delete pollingRefs.current[id];
    }
    // Delete from server (best-effort, don't block UI)
    if (!id.startsWith('tmp_')) {
      try { await deleteAttachment(id); } catch {}
    }
  }, [setAttachments]);

  if (attachments.length === 0) return null;

  return (
    <div
      className="attachment-preview"
      onDrop={handleDrop}
      onDragOver={e => e.preventDefault()}
    >
      {attachments.map(att => (
        <AttachmentChip
          key={att.id}
          attachment={att}
          onRemove={handleRemove}
        />
      ))}
      {/* Hidden file input re-triggered by AttachButton */}
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept={ACCEPT}
        onChange={handleInputChange}
        style={{ display: 'none' }}
      />
    </div>
  );
}

// Export helper so AttachButton can open the file dialog
export { ACCEPT };
