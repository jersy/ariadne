package com.webank.asmanalysis.asm.builder;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.HashMap;

/**
 * Immutable value object containing method metadata.
 *
 * <p>This class encapsulates all metadata about a method, providing
 * type-safe access to method properties using the Builder pattern.
 *
 * @author ASM Analysis Team
 * @since 2.0
 */
public class MethodMetadata {
    private final String fqn;
    private final String simpleName;
    private final String descriptor;
    private final List<String> modifiers;
    private final List<String> parameterTypes;
    private final String returnType;
    private final boolean isConstructor;
    private final int lineNumber;

    // Annotation flags
    private final boolean isTransactional;
    private final boolean isAsync;
    private final boolean isScheduled;
    private final boolean isAopAdvice;
    private final boolean isRestEndpoint;
    private final boolean isBeanMethod;
    private final boolean hasMyBatisAnnotation;

    // Additional properties
    private final Map<String, Object> attributes;

    private MethodMetadata(Builder builder) {
        this.fqn = builder.fqn;
        this.simpleName = builder.simpleName;
        this.descriptor = builder.descriptor;
        this.modifiers = Collections.unmodifiableList(new ArrayList<>(builder.modifiers));
        this.parameterTypes = Collections.unmodifiableList(new ArrayList<>(builder.parameterTypes));
        this.returnType = builder.returnType;
        this.isConstructor = builder.isConstructor;
        this.lineNumber = builder.lineNumber;

        this.isTransactional = builder.isTransactional;
        this.isAsync = builder.isAsync;
        this.isScheduled = builder.isScheduled;
        this.isAopAdvice = builder.isAopAdvice;
        this.isRestEndpoint = builder.isRestEndpoint;
        this.isBeanMethod = builder.isBeanMethod;
        this.hasMyBatisAnnotation = builder.hasMyBatisAnnotation;

        this.attributes = Collections.unmodifiableMap(new HashMap<>(builder.attributes));
    }

    // Getters
    public String getFqn() { return fqn; }
    public String getSimpleName() { return simpleName; }
    public String getDescriptor() { return descriptor; }
    public List<String> getModifiers() { return modifiers; }
    public List<String> getParameterTypes() { return parameterTypes; }
    public String getReturnType() { return returnType; }
    public boolean isConstructor() { return isConstructor; }
    public int getLineNumber() { return lineNumber; }

    public boolean isTransactional() { return isTransactional; }
    public boolean isAsync() { return isAsync; }
    public boolean isScheduled() { return isScheduled; }
    public boolean isAopAdvice() { return isAopAdvice; }
    public boolean isRestEndpoint() { return isRestEndpoint; }
    public boolean isBeanMethod() { return isBeanMethod; }
    public boolean hasMyBatisAnnotation() { return hasMyBatisAnnotation; }

    public Map<String, Object> getAttributes() { return attributes; }
    public Object getAttribute(String key) { return attributes.get(key); }

    /**
     * Creates a new builder for MethodMetadata.
     */
    public static Builder builder() {
        return new Builder();
    }

    /**
     * Builder class for MethodMetadata.
     */
    public static class Builder {
        // Required parameters
        private String fqn;
        private String simpleName;
        private String descriptor;

        // Optional parameters - initialized with default values
        private List<String> modifiers = new ArrayList<>();
        private List<String> parameterTypes = new ArrayList<>();
        private String returnType = "";
        private boolean isConstructor = false;
        private int lineNumber = -1;

        // Annotation flags
        private boolean isTransactional = false;
        private boolean isAsync = false;
        private boolean isScheduled = false;
        private boolean isAopAdvice = false;
        private boolean isRestEndpoint = false;
        private boolean isBeanMethod = false;
        private boolean hasMyBatisAnnotation = false;

        // Additional properties
        private Map<String, Object> attributes = new HashMap<>();

        public Builder() {}

        public Builder fqn(String fqn) {
            this.fqn = fqn;
            return this;
        }

        public Builder simpleName(String simpleName) {
            this.simpleName = simpleName;
            return this;
        }

        public Builder descriptor(String descriptor) {
            this.descriptor = descriptor;
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

        public Builder parameterTypes(List<String> parameterTypes) {
            this.parameterTypes = parameterTypes != null ? new ArrayList<>(parameterTypes) : new ArrayList<>();
            return this;
        }

        public Builder addParameterType(String parameterType) {
            this.parameterTypes.add(parameterType);
            return this;
        }

        public Builder returnType(String returnType) {
            this.returnType = returnType != null ? returnType : "";
            return this;
        }

        public Builder isConstructor(boolean isConstructor) {
            this.isConstructor = isConstructor;
            return this;
        }

        public Builder lineNumber(int lineNumber) {
            this.lineNumber = lineNumber;
            return this;
        }

        // Annotation flag setters
        public Builder isTransactional(boolean isTransactional) {
            this.isTransactional = isTransactional;
            return this;
        }

        public Builder isAsync(boolean isAsync) {
            this.isAsync = isAsync;
            return this;
        }

        public Builder isScheduled(boolean isScheduled) {
            this.isScheduled = isScheduled;
            return this;
        }

        public Builder isAopAdvice(boolean isAopAdvice) {
            this.isAopAdvice = isAopAdvice;
            return this;
        }

        public Builder isRestEndpoint(boolean isRestEndpoint) {
            this.isRestEndpoint = isRestEndpoint;
            return this;
        }

        public Builder isBeanMethod(boolean isBeanMethod) {
            this.isBeanMethod = isBeanMethod;
            return this;
        }

        public Builder hasMyBatisAnnotation(boolean hasMyBatisAnnotation) {
            this.hasMyBatisAnnotation = hasMyBatisAnnotation;
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
         * Builds the MethodMetadata instance.
         *
         * @return A new MethodMetadata instance
         * @throws IllegalStateException if required fields are not set
         */
        public MethodMetadata build() {
            if (fqn == null) {
                throw new IllegalStateException("fqn is required");
            }
            if (simpleName == null) {
                throw new IllegalStateException("simpleName is required");
            }
            if (descriptor == null) {
                throw new IllegalStateException("descriptor is required");
            }

            return new MethodMetadata(this);
        }
    }

    @Override
    public String toString() {
        return "MethodMetadata{" +
                "fqn='" + fqn + '\'' +
                ", simpleName='" + simpleName + '\'' +
                ", isConstructor=" + isConstructor +
                ", isTransactional=" + isTransactional +
                ", isAsync=" + isAsync +
                ", modifiers=" + modifiers +
                '}';
    }
}
