import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Alert, Box, Button, Card, CardContent, Stack, TextField, Typography } from "@mui/material";
import { changePassword } from "../services/authService";

function ChangePasswordPage() {
  const navigate = useNavigate();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError(""); setSuccess("");
    if (newPassword.length < 8) { setError("New password must contain at least 8 characters."); return; }
    if (newPassword !== confirmPassword) { setError("New password and confirmation do not match."); return; }
    try {
      setSubmitting(true);
      await changePassword({ current_password: currentPassword, new_password: newPassword });
      setCurrentPassword(""); setNewPassword(""); setConfirmPassword("");
      setSuccess("Password changed successfully.");
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Unable to change password.");
    } finally { setSubmitting(false); }
  };

  return (
    <Box sx={{ py: 4 }}>
  <Card sx={{ maxWidth: 560, mx: "auto" }}>
    <CardContent>
      <Typography
        variant="h5"
        gutterBottom
        sx={{ fontWeight: 700 }}
      >
        Change Password
      </Typography>

      <Typography
        variant="body2"
        color="text.secondary"
        sx={{ mb: 3 }}
      >
        Update the password used to sign in to your account.
      </Typography>

      <Box component="form" onSubmit={handleSubmit}>
        <Stack spacing={2}>
          {error && <Alert severity="error">{error}</Alert>}
          {success && <Alert severity="success">{success}</Alert>}

          <TextField
            label="Current Password"
            type="password"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            required
            fullWidth
            autoComplete="current-password"
          />

          <TextField
            label="New Password"
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            required
            fullWidth
            slotProps={{
              htmlInput: {
                minLength: 8,
              },
            }}
            autoComplete="new-password"
          />

          <TextField
            label="Confirm New Password"
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            required
            fullWidth
            autoComplete="new-password"
          />

          <Stack
            direction="row"
            spacing={1}
            sx={{ justifyContent: "flex-end" }}
          >
            <Button
              type="button"
              onClick={() => navigate(-1)}
              disabled={submitting}
            >
              Cancel
            </Button>

            <Button
              type="submit"
              variant="contained"
              disabled={submitting}
            >
              {submitting ? "Changing..." : "Change Password"}
            </Button>
          </Stack>
        </Stack>
      </Box>
    </CardContent>
  </Card>
</Box>
  );
}
export default ChangePasswordPage;
