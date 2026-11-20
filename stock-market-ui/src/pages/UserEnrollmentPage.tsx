import { useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import PersonAddAlt1Icon from "@mui/icons-material/PersonAddAlt1";

import { enrollUser } from "../services/adminUserService";
import type { UserRole } from "../types/auth";
import { useNavigate } from "react-router-dom";

function UserEnrollmentPage() {
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [temporaryPassword, setTemporaryPassword] =
    useState("");
  const [confirmPassword, setConfirmPassword] =
    useState("");
  const [role, setRole] =
    useState<UserRole>("VIEWER");

  const [submitting, setSubmitting] = useState(false);
  const [successMessage, setSuccessMessage] =
    useState("");
  const [errorMessage, setErrorMessage] =
    useState("");

  const resetForm = () => {
    setEmail("");
    setFullName("");
    setTemporaryPassword("");
    setConfirmPassword("");
    setRole("VIEWER");
  };

  const navigate = useNavigate();

  const handleSubmit = async (
    event: React.FormEvent
  ) => {
    event.preventDefault();

    setSuccessMessage("");
    setErrorMessage("");

    const normalizedEmail = email.trim();

    if (!normalizedEmail) {
      setErrorMessage("Email is required.");
      return;
    }

    if (temporaryPassword.length < 8) {
      setErrorMessage(
        "Temporary password must contain at least 8 characters."
      );
      return;
    }

    if (temporaryPassword !== confirmPassword) {
      setErrorMessage(
        "Temporary password and confirmation do not match."
      );
      return;
    }

    try {
      setSubmitting(true);

      const createdUser = await enrollUser({
        email: normalizedEmail,
        full_name: fullName.trim() || undefined,
        temporary_password: temporaryPassword,
        role,
      });

      setSuccessMessage(
        `User ${createdUser.email} enrolled successfully.`
      );

      resetForm();

      setTimeout(() => {
        navigate("/login", { replace: true });
        }, 1000);

    } catch (error: any) {
      const detail =
        error?.response?.data?.detail;

      setErrorMessage(
        typeof detail === "string"
          ? detail
          : "Unable to enroll user."
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Box sx={{ py: 3 }}>
      <Typography
        variant="h5"
        sx={{ fontWeight: 700, mb: 0.5 }}
      >
        User Enrollment
      </Typography>

      <Typography
        variant="body2"
        color="text.secondary"
        sx={{ mb: 3 }}
      >
        Create an application account and assign its
        access role.
      </Typography>

      <Card sx={{ maxWidth: 700 }}>
        <CardContent>
          <Box
            component="form"
            onSubmit={handleSubmit}
          >
            <Stack spacing={2.5}>
              {successMessage && (
                <Alert severity="success">
                  {successMessage}
                </Alert>
              )}

              {errorMessage && (
                <Alert severity="error">
                  {errorMessage}
                </Alert>
              )}

              <TextField
                label="Email"
                type="email"
                value={email}
                onChange={(event) =>
                  setEmail(event.target.value)
                }
                required
                fullWidth
                autoComplete="off"
              />

              <TextField
                label="Full Name"
                value={fullName}
                onChange={(event) =>
                  setFullName(event.target.value)
                }
                fullWidth
                slotProps={{
                    htmlInput: {
                        maxLength: 255,
                    },
                    }}
              />

              <TextField
                label="Temporary Password"
                type="password"
                value={temporaryPassword}
                onChange={(event) =>
                  setTemporaryPassword(
                    event.target.value
                  )
                }
                required
                fullWidth
                    slotProps={{
                    htmlInput: {
                        minLength: 8,
                        maxLength: 72,
                    },
                    }}
                autoComplete="new-password"
                helperText="8–72 characters"
              />

              <TextField
                label="Confirm Temporary Password"
                type="password"
                value={confirmPassword}
                onChange={(event) =>
                  setConfirmPassword(
                    event.target.value
                  )
                }
                required
                fullWidth
                autoComplete="new-password"
              />

              <FormControl fullWidth>
                <InputLabel id="user-role-label">
                  Role
                </InputLabel>

                <Select
                  labelId="user-role-label"
                  label="Role"
                  value={role}
                  onChange={(event) =>
                    setRole(
                      event.target.value as UserRole
                    )
                  }
                >
                  <MenuItem value="VIEWER">
                    VIEWER
                  </MenuItem>

                  <MenuItem value="ADMIN">
                    ADMIN
                  </MenuItem>
                </Select>
              </FormControl>

              <Alert severity="info">
                VIEWER is the default role. ADMIN
                accounts have administrative
                privileges.
              </Alert>

                    <Box
                    sx={{
                        display: "flex",
                        justifyContent: "flex-end",
                    }}
                    >
                    <Button
                        type="submit"
                        variant="contained"
                        startIcon={<PersonAddAlt1Icon />}
                        disabled={submitting}
                    >
                        {submitting
                        ? "Enrolling..."
                        : "Enroll User"}
                    </Button>
                    </Box>

            </Stack>
          </Box>
        </CardContent>
      </Card>
    </Box>
  );
}

export default UserEnrollmentPage;