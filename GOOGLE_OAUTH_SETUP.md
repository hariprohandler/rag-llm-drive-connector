# Google OAuth Setup Guide

## Redirect URI Configuration

This application uses **two different redirect URIs** for Google OAuth:

1. **Login OAuth**: `http://localhost:8000/auth/callback/google`
   - Used for user authentication/login
   - Configured via `GOOGLE_REDIRECT_URI` environment variable

2. **Drive Connection OAuth**: `http://localhost:8000/api/drive/callback/google`
   - Used for connecting Google Drive for document ingestion
   - Automatically generated from `BACKEND_BASE_URL`

## Google Cloud Console Configuration

You **must add both redirect URIs** to your Google Cloud Console OAuth 2.0 Client:

### Steps:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Navigate to **APIs & Services** > **Credentials**
3. Click on your OAuth 2.0 Client ID
4. Under **Authorized redirect URIs**, add:
   - `http://localhost:8000/auth/callback/google` (for login)
   - `http://localhost:8000/api/drive/callback/google` (for drive connection)

### For Production:

When deploying to production, add the production URLs:
- `https://your-domain.com/auth/callback/google`
- `https://your-domain.com/api/drive/callback/google`

## Environment Variables

Make sure your `.env.development` or `.env` file has:

```bash
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/callback/google
BACKEND_BASE_URL=http://localhost:8000
```

## Common Errors

### Error 400: redirect_uri_mismatch

This error occurs when the redirect URI in your request doesn't match any of the authorized redirect URIs in Google Cloud Console.

**Solution**: Ensure both redirect URIs are added to Google Cloud Console as described above.

### Testing

After adding the redirect URIs:
1. Restart your application
2. Try logging in with Google
3. Try connecting Google Drive

Both should work without the `redirect_uri_mismatch` error.

