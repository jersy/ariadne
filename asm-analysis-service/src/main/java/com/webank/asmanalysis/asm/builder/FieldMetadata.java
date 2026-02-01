package com.webank.asmanalysis.asm.builder;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.HashMap;

/**
 * Immutable value object containing field metadata.
 *
 * <p>This class encapsulates all metadata about a field, providing
 * type-safe access to field properties using the Builder pattern.
 *
 * @author ASM Analysis Team
 * @since 2.0
 */
public class FieldMetadata {
    private final String fieldName;
    private final String className;
    private final String fieldType;
    private final String descriptor;
    private final List<String> modifiers;
    private final Object initialValue;

    // Dependency injection flags
    private final boolean isAutowired;
    private final boolean isInject;
    private final boolean isResource;
    private final boolean hasValue;
    private final boolean hasQualifier;
    private final String injectionType;
    private final String qualifierValue;
    private final String configKey;

    // Additional properties
    private final Map<String, Object> attributes;

    private FieldMetadata(Builder builder) {
        this.fieldName = builder.fieldName;
        this.className = builder.className;
        this.fieldType = builder.fieldType;
        this.descriptor = builder.descriptor;
        this.modifiers = Collections.unmodifiableList(new ArrayList<>(builder.modifiers));
        this.initialValue = builder.initialValue;

        this.isAutowired = builder.isAutowired;
        this.isInject = builder.isInject;
        this.isResource = builder.isResource;
        this.hasValue = builder.hasValue;
        this.hasQualifier = builder.hasQualifier;
        this.injectionType = builder.injectionType;
        this.qualifierValue = builder.qualifierValue;
        this.configKey = builder.configKey;

        this.attributes = Collections.unmodifiableMap(new HashMap<>(builder.attributes));
    }

    // Getters
    public String getFieldName() { return fieldName; }
    public String getClassName() { return className; }
    public String getFieldType() { return fieldType; }
    public String getDescriptor() { return descriptor; }
    public List<String> getModifiers() { return modifiers; }
    public Object getInitialValue() { return initialValue; }

    public boolean isAutowired() { return isAutowired; }
    public boolean isInject() { return isInject; }
    public boolean isResource() { return isResource; }
    public boolean hasValue() { return hasValue; }
    public boolean hasQualifier() { return hasQualifier; }
    public String getInjectionType() { return injectionType; }
    public String getQualifierValue() { return qualifierValue; }
    public String getConfigKey() { return configKey; }

    public Map<String, Object> getAttributes() { return attributes; }
    public Object getAttribute(String key) { return attributes.get(key); }

    /**
     * Creates a new builder for FieldMetadata.
     */
    public static Builder builder() {
        return new Builder();
    }

    /**
     * Builder class for FieldMetadata.
     */
    public static class Builder {
        // Required parameters
        private String fieldName;
        private String className;

        // Optional parameters - initialized with default values
        private String fieldType = "";
        private String descriptor = "";
        private List<String> modifiers = new ArrayList<>();
        private Object initialValue = null;

        // Dependency injection flags
        private boolean isAutowired = false;
        private boolean isInject = false;
        private boolean isResource = false;
        private boolean hasValue = false;
        private boolean hasQualifier = false;
        private String injectionType = "";
        private String qualifierValue = "";
        private String configKey = "";

        // Additional properties
        private Map<String, Object> attributes = new HashMap<>();

        public Builder() {}

        public Builder fieldName(String fieldName) {
            this.fieldName = fieldName;
            return this;
        }

        public Builder className(String className) {
            this.className = className;
            return this;
        }

        public Builder fieldType(String fieldType) {
            this.fieldType = fieldType != null ? fieldType : "";
            return this;
        }

        public Builder descriptor(String descriptor) {
            this.descriptor = descriptor != null ? descriptor : "";
            return this;
        }

        public Builder modifiers(List<String> modifiers) {
            this.modifiers = modifiers != null ? new ArrayList<>(modifiers) : new ArrayList<>();
            return this;
        }

        public Builder addModifier(String modifier) {
            this.modifiers.add(modifier);
            return this;
        }

        public Builder initialValue(Object initialValue) {
            this.initialValue = initialValue;
            return this;
        }

        // Dependency injection setters
        public Builder isAutowired(boolean isAutowired) {
            this.isAutowired = isAutowired;
            if (isAutowired) {
                this.injectionType = "autowired";
            }
            return this;
        }

        public Builder isInject(boolean isInject) {
            this.isInject = isInject;
            if (isInject) {
                this.injectionType = "inject";
            }
            return this;
        }

        public Builder isResource(boolean isResource) {
            this.isResource = isResource;
            if (isResource) {
                this.injectionType = "resource";
            }
            return this;
        }

        public Builder hasValue(boolean hasValue) {
            this.hasValue = hasValue;
            return this;
        }

        public Builder hasQualifier(boolean hasQualifier) {
            this.hasQualifier = hasQualifier;
            return this;
        }

        public Builder injectionType(String injectionType) {
            this.injectionType = injectionType != null ? injectionType : "";
            return this;
        }

        public Builder qualifierValue(String qualifierValue) {
            this.qualifierValue = qualifierValue != null ? qualifierValue : "";
            this.hasQualifier = !qualifierValue.isEmpty();
            return this;
        }

        public Builder configKey(String configKey) {
            this.configKey = configKey != null ? configKey : "";
            this.hasValue = !configKey.isEmpty();
            return this;
        }

        // Attribute setters
        public Builder putAttribute(String key, Object value) {
            this.attributes.put(key, value);
            return this;
        }

        public Builder attributes(Map<String, Object> attributes) {
            this.attributes = attributes != null ? new HashMap<>(attributes) : new HashMap<>();
            return this;
        }

        /**
         * Builds the FieldMetadata instance.
         *
         * @return A new FieldMetadata instance
         * @throws IllegalStateException if required fields are not set
         */
        public FieldMetadata build() {
            if (fieldName == null) {
                throw new IllegalStateException("fieldName is required");
            }
            if (className == null) {
                throw new IllegalStateException("className is required");
            }

            return new FieldMetadata(this);
        }
    }

    @Override
    public String toString() {
        return "FieldMetadata{" +
                "fieldName='" + fieldName + '\'' +
                ", className='" + className + '\'' +
                ", fieldType='" + fieldType + '\'' +
                ", injectionType='" + injectionType + '\'' +
                ", isAutowired=" + isAutowired +
                ", hasValue=" + hasValue +
                ", modifiers=" + modifiers +
                '}';
    }
}
