package com.webank.asmanalysis.asm.utils;

import java.util.Collection;
import java.util.Map;

/**
 * Utility class for input validation.
 *
 * <p>Provides common validation methods to ensure data integrity throughout the analysis process.
 *
 * @author ASM Analysis Team
 * @since 2.0
 */
public final class ValidationUtils {

    private ValidationUtils() {
        // Utility class - prevent instantiation
    }

    /**
     * Validates that a string is not null or empty.
     *
     * @param value the string to validate
     * @param paramName the parameter name for error messages
     * @throws IllegalArgumentException if validation fails
     */
    public static void requireNonEmpty(String value, String paramName) {
        if (value == null) {
            throw new IllegalArgumentException(paramName + " cannot be null");
        }
        if (value.trim().isEmpty()) {
            throw new IllegalArgumentException(paramName + " cannot be empty");
        }
    }

    /**
     * Validates that an object is not null.
     *
     * @param value the object to validate
     * @param paramName the parameter name for error messages
     * @throws IllegalArgumentException if validation fails
     */
    public static void requireNonNull(Object value, String paramName) {
        if (value == null) {
            throw new IllegalArgumentException(paramName + " cannot be null");
        }
    }

    /**
     * Validates that a collection is not null or empty.
     *
     * @param collection the collection to validate
     * @param paramName the parameter name for error messages
     * @throws IllegalArgumentException if validation fails
     */
    public static void requireNonEmpty(Collection<?> collection, String paramName) {
        if (collection == null) {
            throw new IllegalArgumentException(paramName + " cannot be null");
        }
        if (collection.isEmpty()) {
            throw new IllegalArgumentException(paramName + " cannot be empty");
        }
    }

    /**
     * Validates that a map is not null or empty.
     *
     * @param map the map to validate
     * @param paramName the parameter name for error messages
     * @throws IllegalArgumentException if validation fails
     */
    public static void requireNonEmpty(Map<?, ?> map, String paramName) {
        if (map == null) {
            throw new IllegalArgumentException(paramName + " cannot be null");
        }
        if (map.isEmpty()) {
            throw new IllegalArgumentException(paramName + " cannot be empty");
        }
    }

    /**
     * Validates that a number is positive.
     *
     * @param value the number to validate
     * @param paramName the parameter name for error messages
     * @throws IllegalArgumentException if validation fails
     */
    public static void requirePositive(int value, String paramName) {
        if (value <= 0) {
            throw new IllegalArgumentException(paramName + " must be positive, but was: " + value);
        }
    }

    /**
     * Validates that a string is a valid Java identifier.
     *
     * @param identifier the identifier to validate
     * @param paramName the parameter name for error messages
     * @throws IllegalArgumentException if validation fails
     */
    public static void requireValidIdentifier(String identifier, String paramName) {
        requireNonEmpty(identifier, paramName);

        if (!Character.isJavaIdentifierStart(identifier.charAt(0))) {
            throw new IllegalArgumentException(paramName + " must start with a valid Java identifier character: " + identifier);
        }

        for (int i = 1; i < identifier.length(); i++) {
            if (!Character.isJavaIdentifierPart(identifier.charAt(i))) {
                throw new IllegalArgumentException(paramName + " contains invalid Java identifier characters: " + identifier);
            }
        }
    }

    /**
     * Validates that a string is a valid fully qualified Java class name.
     *
     * @param className the class name to validate
     * @param paramName the parameter name for error messages
     * @throws IllegalArgumentException if validation fails
     */
    public static void requireValidClassName(String className, String paramName) {
        requireNonEmpty(className, paramName);

        // Must contain at least one dot for package
        int lastDot = className.lastIndexOf('.');
        if (lastDot <= 0 || lastDot == className.length() - 1) {
            throw new IllegalArgumentException(paramName + " must be a valid fully qualified class name with package: " + className);
        }

        // Validate each part
        String[] parts = className.split("\\.");
        for (String part : parts) {
            requireValidIdentifier(part, paramName + " part");
        }
    }

    /**
     * Validates that a value is within a specified range.
     *
     * @param value the value to validate
     * @param min the minimum allowed value (inclusive)
     * @param max the maximum allowed value (inclusive)
     * @param paramName the parameter name for error messages
     * @throws IllegalArgumentException if validation fails
     */
    public static void requireInRange(int value, int min, int max, String paramName) {
        if (value < min || value > max) {
            throw new IllegalArgumentException(paramName + " must be between " + min + " and " + max + ", but was: " + value);
        }
    }

    /**
     * Checks if a string is null or empty without throwing an exception.
     *
     * @param value the string to check
     * @return true if the string is null or empty
     */
    public static boolean isNullOrEmpty(String value) {
        return value == null || value.trim().isEmpty();
    }

    /**
     * Checks if a collection is null or empty without throwing an exception.
     *
     * @param collection the collection to check
     * @return true if the collection is null or empty
     */
    public static boolean isNullOrEmpty(Collection<?> collection) {
        return collection == null || collection.isEmpty();
    }

    /**
     * Checks if an object is null without throwing an exception.
     *
     * @param value the object to check
     * @return true if the object is null
     */
    public static boolean isNull(Object value) {
        return value == null;
    }
}
