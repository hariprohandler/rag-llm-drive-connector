import React, { useState } from "react";
import { BACKEND_BASE_URL } from "../api.js";

const DocumentsPage = () => {
  const [status, setStatus] = useState(null);

  const handleUpload = async (e) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    const formData = new FormData();
    Array.from(files).forEach((file) => formData.append("files", file));

    try {
      const res = await fetch(`${BACKEND_BASE_URL}/api/ingest/upload`, {
        method: "POST",
        credentials: "include",
        body: formData
      });
      if (!res.ok) {
        throw new Error(await res.text());
      }
      const data = await res.json();
      setStatus(
        `Uploaded and ingested successfully. Knowledge base ID: ${data.knowledge_base_id}`
      );
    } catch (e) {
      setStatus(`Error: ${e.message}`);
    }
  };

  return (
    <div>
      <h1>Document Management</h1>
      <p>Upload and manage documents for RAG-based queries.</p>
      <input type="file" multiple onChange={handleUpload} />
      {status && <p style={{ marginTop: 12 }}>{status}</p>}
    </div>
  );
};

export default DocumentsPage;


