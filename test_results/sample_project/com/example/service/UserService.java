package com.example.service;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.Map;
import java.util.regex.Pattern;

/**
 * User service for handling user authentication and registration.
 */
public class UserService {
    
    private static final int MIN_PASSWORD_LENGTH = 8;
    private static final Pattern EMAIL_PATTERN = 
        Pattern.compile("^[A-Za-z0-9+_.-]+@(.+)$");
    
    private final Map<String, UserData> users = new HashMap<>();
    
    /**
     * Authenticate user with username and password.
     * 
     * @param username the username
     * @param password the raw password
     * @return true if authentication successful
     * @throws AuthenticationException if credentials invalid
     */
    public boolean authenticate(String username, String password) {
        if (username == null || username.trim().isEmpty()) {
            throw new IllegalArgumentException("Username cannot be empty");
        }
        
        UserData user = users.get(username);
        if (user == null) {
            throw new AuthenticationException("User not found: " + username);
        }
        
        if (!user.isActive()) {
            throw new AuthenticationException("Account is disabled: " + username);
        }
        
        if (!user.checkPassword(password)) {
            throw new AuthenticationException("Invalid password for: " + username);
        }
        
        // Update last login time
        user.setLastLoginTime(LocalDateTime.now());
        
        return true;
    }
    
    /**
     * Register a new user account.
     * 
     * @param username the desired username
     * @param email the email address
     * @param password the raw password
     * @return the created user
     * @throws RegistrationException if registration fails
     */
    public UserData register(String username, String email, String password) {
        // Validate username uniqueness
        if (users.containsKey(username)) {
            throw new RegistrationException("Username already exists: " + username);
        }
        
        // Validate email format
        if (!EMAIL_PATTERN.matcher(email).matches()) {
            throw new IllegalArgumentException("Invalid email format");
        }
        
        // Validate password strength
        if (password == null || password.length() < MIN_PASSWORD_LENGTH) {
            throw new IllegalArgumentException("Password must be at least 8 characters");
        }
        
        // Create new user
        UserData user = new UserData();
        user.setUsername(username);
        user.setEmail(email);
        user.setPassword(hashPassword(password));
        user.setActive(true);
        user.setCreatedTime(LocalDateTime.now());
        
        // Save to in-memory store
        users.put(username, user);
        
        return user;
    }
    
    /**
     * Change user password.
     * 
     * @param username the username
     * @param oldPassword the current password
     * @param newPassword the new password
     * @return true if password changed successfully
     */
    public boolean changePassword(String username, String oldPassword, String newPassword) {
        UserData user = users.get(username);
        if (user == null) {
            throw new AuthenticationException("User not found: " + username);
        }
        
        // Verify old password
        if (!user.checkPassword(oldPassword)) {
            throw new AuthenticationException("Current password is incorrect");
        }
        
        // Validate new password
        if (newPassword == null || newPassword.length() < MIN_PASSWORD_LENGTH) {
            throw new IllegalArgumentException("New password must be at least 8 characters");
        }
        
        // Update password
        user.setPassword(hashPassword(newPassword));
        user.setPasswordChangedTime(LocalDateTime.now());
        
        return true;
    }
    
    private String hashPassword(String password) {
        // Simple hash for demonstration
        return Integer.toHexString(password.hashCode());
    }
    
    // Inner class for user data
    public static class UserData {
        private String username;
        private String email;
        private String password;
        private boolean active;
        private LocalDateTime createdTime;
        private LocalDateTime lastLoginTime;
        private LocalDateTime passwordChangedTime;
        
        public String getUsername() { return username; }
        public void setUsername(String username) { this.username = username; }
        public String getEmail() { return email; }
        public void setEmail(String email) { this.email = email; }
        public boolean isActive() { return active; }
        public void setActive(boolean active) { this.active = active; }
        public LocalDateTime getCreatedTime() { return createdTime; }
        public void setCreatedTime(LocalDateTime time) { createdTime = time; }
        public LocalDateTime getLastLoginTime() { return lastLoginTime; }
        public void setLastLoginTime(LocalDateTime time) { lastLoginTime = time; }
        public LocalDateTime getPasswordChangedTime() { return passwordChangedTime; }
        public void setPasswordChangedTime(LocalDateTime time) { passwordChangedTime = time; }
        
        public void setPassword(String password) { this.password = password; }
        public boolean checkPassword(String input) {
            return this.password.equals(hashPassword(input));
        }
        private static String hashPassword(String password) {
            return Integer.toHexString(password.hashCode());
        }
    }
}

class AuthenticationException extends RuntimeException {
    public AuthenticationException(String message) { super(message); }
}

class RegistrationException extends RuntimeException {
    public RegistrationException(String message) { super(message); }
}
