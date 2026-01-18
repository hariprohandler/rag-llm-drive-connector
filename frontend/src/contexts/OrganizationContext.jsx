import React, { createContext, useContext, useState, useEffect } from "react";
import { api } from "../api.js";

const OrganizationContext = createContext({
  organizationName: "Anukara",
  setOrganizationName: () => {},
  loading: false,
});

export const useOrganization = () => useContext(OrganizationContext);

export const OrganizationProvider = ({ children }) => {
  const [organizationName, setOrganizationNameState] = useState("Anukara");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Load organization name from localStorage first (for instant display)
    const stored = localStorage.getItem("organizationName");
    if (stored) {
      setOrganizationNameState(stored);
    }

    // Then try to load from API
    api
      .getOrganizationSettings()
      .then((data) => {
        if (data.organization_name) {
          setOrganizationNameState(data.organization_name);
          localStorage.setItem("organizationName", data.organization_name);
        }
      })
      .catch(() => {
        // If API fails, use localStorage or default
        if (!stored) {
          setOrganizationNameState("Anukara");
        }
      })
      .finally(() => setLoading(false));
  }, []);

  const setOrganizationName = async (name) => {
    setOrganizationNameState(name);
    localStorage.setItem("organizationName", name);
    
    // Save to backend
    try {
      await api.updateOrganizationSettings({ organization_name: name });
    } catch (error) {
      console.error("Failed to save organization name:", error);
    }
  };

  return (
    <OrganizationContext.Provider
      value={{
        organizationName,
        setOrganizationName,
        loading,
      }}
    >
      {children}
    </OrganizationContext.Provider>
  );
};

