import {
  Box,
  CircularProgress,
} from "@mui/material";

import { Navigate } from "react-router-dom";

import { useAuth } from "../context/AuthContext";


function AdminRoute({
  children,
}: {
  children: React.ReactNode;
}) {
  const {
    loading,
    isAuthenticated,
    user,
  } = useAuth();


  if (loading) {
    return (
      <Box
        sx={{
          minHeight: "50vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <CircularProgress />
      </Box>
    );
  }


  if (!isAuthenticated) {
    return (
      <Navigate
        to="/login"
        replace
      />
    );
  }


  if (user?.role !== "ADMIN") {
    return (
      <Navigate
        to="/"
        replace
      />
    );
  }


  return children;
}


export default AdminRoute;