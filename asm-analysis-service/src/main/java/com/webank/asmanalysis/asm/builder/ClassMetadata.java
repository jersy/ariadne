package com.webank.asmanalysis.asm.builder;

import org.objectweb.asm.Opcodes;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.HashMap;

/**
 * Immutable value object containing class metadata.
 *
 * <p>This class encapsulates all metadata about a class, providing
 * type-safe access to class properties using the Builder pattern.
 *
 * @author ASM Analysis Team
 * @since 2.0
 */
public class ClassMetadata {
    private final String className;
    private final String simpleName;
    private final String packageName;
    private final String superClassName;
    private final List<String> interfaces;
    private final List<String> modifiers;
    private final boolean isInterface;
    private final boolean isEnum;
    private final boolean isAbstract;
    private final int version;

    // Spring-specific flags
    private final String springBeanType;
    private final boolean isSpringBean;
    private final boolean isConfiguration;
    private final boolean isController;
    private final boolean isRestController;
    private final boolean isAspect;
    private final boolean needsProxy;

    // Additional properties
    private final Map<String, Object> attributes;

    private ClassMetadata(Builder builder) {
        this.className = builder.className;
        this.simpleName = builder.simpleName;
        this.packageName = builder.packageName;
        this.superClassName = builder.superClassName;
        this.interfaces = Collections.unmodifiableList(new ArrayList<>(builder.interfaces));
        this.modifiers = Collections.unmodifiableList(new ArrayList<>(builder.modifiers));
        this.isInterface = builder.isInterface;
        this.isEnum = builder.isEnum;
        this.isAbstract = builder.isAbstract;
        this.version = builder.version;

        this.springBeanType = builder.springBeanType;
        this.isSpringBean = builder.isSpringBean;
        this.isConfiguration = builder.isConfiguration;
        this.isController = builder.isController;
        this.isRestController = builder.isRestController;
        this.isAspect = builder.isAspect;
        this.needsProxy = builder.needsProxy;

        this.attributes = Collections.unmodifiableMap(new HashMap<>(builder.attributes));
    }

    // Getters
    public String getClassName() { return className; }
    public String getSimpleName() { return simpleName; }
    public String getPackageName() { return packageName; }
    public String getSuperClassName() { return superClassName; }
    public List<String> getInterfaces() { return interfaces; }
    public List<String> getModifiers() { return modifiers; }
    public boolean isInterface() { return isInterface; }
    public boolean isEnum() { return isEnum; }
    public boolean isAbstract() { return isAbstract; }
    public int getVersion() { return version; }

    public String getSpringBeanType() { return springBeanType; }
    public boolean isSpringBean() { return isSpringBean; }
    public boolean isConfiguration() { return isConfiguration; }
    public boolean isController() { return isController; }
    public boolean isRestController() { return isRestController; }
    public boolean isAspect() { return isAspect; }
    public boolean isNeedsProxy() { return needsProxy; }

    public Map<String, Object> getAttributes() { return attributes; }
    public Object getAttribute(String key) { return attributes.get(key); }

    /**
     * Creates a new builder for ClassMetadata.
     */
    public static Builder builder() {
        return new Builder();
    }

    /**
     * Builder class for ClassMetadata.
     */
    public static class Builder {
        // Required parameters
        private String className;
        private String simpleName;

        // Optional parameters - initialized with default values
        private String packageName = "";
        private String superClassName = "java.lang.Object";
        private List<String> interfaces = new ArrayList<>();
        private List<String> modifiers = new ArrayList<>();
        private boolean isInterface = false;
        private boolean isEnum = false;
        private boolean isAbstract = false;
        private int version = Opcodes.V1_8;

        // Spring-specific flags
        private String springBeanType = "";
        private boolean isSpringBean = false;
        private boolean isConfiguration = false;
        private boolean isController = false;
        private boolean isRestController = false;
        private boolean isAspect = false;
        private boolean needsProxy = false;

        // Additional properties
        private Map<String, Object> attributes = new HashMap<>();

        public Builder() {}

        public Builder className(String className) {
            this.className = className;
            // Auto-derive simpleName and packageName
            int lastDot = className.lastIndexOf('.');
            if (lastDot > 0) {
                this.simpleName = className.substring(lastDot + 1);
                this.packageName = className.substring(0, lastDot);
            } else {
                this.simpleName = className;
                this.packageName = "";
            }
            return this;
        }

        public Builder simpleName(String simpleName) {
            this.simpleName = simpleName;
            return this;
        }

        public Builder packageName(String packageName) {
            this.packageName = packageName != null ? packageName : "";
            return this;
        }

        public Builder superClassName(String superClassName) {
            this.superClassName = superClassName != null ? superClassName : "java.lang.Object";
            return this;
        }

        public Builder interfaces(List<String> interfaces) {
            this.interfaces = interfaces != null ? new ArrayList<>(interfaces) : new ArrayList<>();
            return this;
        }

        public Builder addInterface(String iface) {
            this.interfaces.add(iface);
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

        public Builder isInterface(boolean isInterface) {
            this.isInterface = isInterface;
            return this;
        }

        public Builder isEnum(boolean isEnum) {
            this.isEnum = isEnum;
            return this;
        }

        public Builder isAbstract(boolean isAbstract) {
            this.isAbstract = isAbstract;
            return this;
        }

        public Builder version(int version) {
            this.version = version;
            return this;
        }

        // Spring-specific setters
        public Builder springBeanType(String springBeanType) {
            this.springBeanType = springBeanType != null ? springBeanType : "";
            this.isSpringBean = !springBeanType.isEmpty();
            return this;
        }

        public Builder isSpringBean(boolean isSpringBean) {
            this.isSpringBean = isSpringBean;
            return this;
        }

        public Builder isConfiguration(boolean isConfiguration) {
            this.isConfiguration = isConfiguration;
            return this;
        }

        public Builder isController(boolean isController) {
            this.isController = isController;
            return this;
        }

        public Builder isRestController(boolean isRestController) {
            this.isRestController = isRestController;
            return this;
        }

        public Builder isAspect(boolean isAspect) {
            this.isAspect = isAspect;
            return this;
        }

        public Builder needsProxy(boolean needsProxy) {
            this.needsProxy = needsProxy;
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
         * Builds the ClassMetadata instance.
         *
         * @return A new ClassMetadata instance
         * @throws IllegalStateException if required fields are not set
         */
        public ClassMetadata build() {
            if (className == null) {
                throw new IllegalStateException("className is required");
            }
            if (simpleName == null) {
                throw new IllegalStateException("simpleName is required");
            }

            return new ClassMetadata(this);
        }
    }

    @Override
    public String toString() {
        return "ClassMetadata{" +
                "className='" + className + '\'' +
                ", simpleName='" + simpleName + '\'' +
                ", isSpringBean=" + isSpringBean +
                ", springBeanType='" + springBeanType + '\'' +
                ", isController=" + isController +
                ", isRestController=" + isRestController +
                ", isAspect=" + isAspect +
                ", modifiers=" + modifiers +
                '}';
    }
}
