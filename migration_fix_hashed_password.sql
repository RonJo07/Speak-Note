-- Migration to fix hashed_password field for OTP users
-- This allows OTP-only users to have NULL hashed_password

-- Step 1: Update the hashed_password column to allow NULL values
ALTER TABLE users ALTER COLUMN hashed_password DROP NOT NULL;

-- Step 2: Add a comment to document the change
COMMENT ON COLUMN users.hashed_password IS 'Can be NULL for OTP-only users who do not have a password';

-- Step 3: Add OTP-related columns if they don't exist
-- Check if otp column exists, if not add it
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'users' AND column_name = 'otp') THEN
        ALTER TABLE users ADD COLUMN otp VARCHAR;
    END IF;
END $$;

-- Check if otp_expires_at column exists, if not add it
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'users' AND column_name = 'otp_expires_at') THEN
        ALTER TABLE users ADD COLUMN otp_expires_at TIMESTAMP WITH TIME ZONE;
    END IF;
END $$;

-- Step 4: Add comments for OTP columns
COMMENT ON COLUMN users.otp IS 'Temporary OTP code for authentication';
COMMENT ON COLUMN users.otp_expires_at IS 'Expiration timestamp for OTP';

-- Step 5: Verify the changes
SELECT 
    column_name, 
    is_nullable, 
    data_type,
    column_default
FROM information_schema.columns 
WHERE table_name = 'users' 
ORDER BY ordinal_position; 