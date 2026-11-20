import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Paper,
  Stack,
  TextField,
  Typography,
} from "@mui/material";

import {
  useState,
  type FormEvent,
} from "react";

import {
  Navigate,
  useNavigate,
} from "react-router-dom";

import axios from "axios";

import { useAuth } from "../context/AuthContext";


function LoginPage() {
  const navigate = useNavigate();

  const {
    login,
    isAuthenticated,
  } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [submitting, setSubmitting] =
    useState(false);

  const [error, setError] =
    useState<string | null>(null);


  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }


  const handleSubmit = async (
    event: FormEvent<HTMLFormElement>
  ) => {
    event.preventDefault();

    setError(null);
    setSubmitting(true);

    try {
      await login({
        email: email.trim(),
        password,
      });

      navigate("/", {
        replace: true,
      });
    } catch (err) {
      if (axios.isAxiosError(err)) {
        const detail =
          err.response?.data?.detail;

        setError(
          typeof detail === "string"
            ? detail
            : "Unable to sign in"
        );
      } else {
        setError("Unable to sign in");
      }
    } finally {
      setSubmitting(false);
    }
  };


  return (
    <Box
      sx={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        bgcolor: "#f5f7fa",
        px: 2,
      }}
    >
      <Paper
        elevation={3}
        sx={{
          width: "100%",
          maxWidth: 430,
          p: 4,
          borderRadius: 2,
        }}
      >
        <Stack spacing={3}>
          <Box>
            <Typography
            variant="h5"
            sx={{
                fontWeight: 700,
            }}
            >
            Stock Decision Engine
            </Typography>

                <Typography
                variant="body2"
                color="text.secondary"
                sx={{
                    mt: 0.75,
                }}
                >
                Sign in to continue
                </Typography>
          </Box>


          {error && (
            <Alert severity="error">
              {error}
            </Alert>
          )}


          <Box
            component="form"
            onSubmit={handleSubmit}
          >
            <Stack spacing={2.25}>
              <TextField
                label="Email"
                type="email"
                value={email}
                onChange={(event) =>
                  setEmail(event.target.value)
                }
                autoComplete="username"
                required
                fullWidth
              />

              <TextField
                label="Password"
                type="password"
                value={password}
                onChange={(event) =>
                  setPassword(event.target.value)
                }
                autoComplete="current-password"
                required
                fullWidth
              />

              <Button
                type="submit"
                variant="contained"
                size="large"
                disabled={submitting}
                fullWidth
              >
                {submitting ? (
                  <CircularProgress
                    size={22}
                    color="inherit"
                  />
                ) : (
                  "Sign In"
                )}
              </Button>
            </Stack>
          </Box>
        </Stack>
      </Paper>
    </Box>
  );
}


export default LoginPage;