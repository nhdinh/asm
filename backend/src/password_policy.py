"""Password policy validation"""
import re
from models import SystemSetting


class PasswordPolicy:
    """Password policy validator"""

    @staticmethod
    def get_policy_settings():
        """Get password policy settings from database"""
        settings = {}

        # Default values
        defaults = {
            'password_min_length': {'value': '8', 'type': 'int'},
            'password_require_uppercase': {'value': 'true', 'type': 'bool'},
            'password_require_lowercase': {'value': 'true', 'type': 'bool'},
            'password_require_digit': {'value': 'true', 'type': 'bool'},
            'password_require_special': {'value': 'true', 'type': 'bool'},
        }

        for key, default in defaults.items():
            setting = SystemSetting.query.filter_by(key=key).first()
            if setting:
                if default['type'] == 'int':
                    settings[key] = int(setting.value)
                elif default['type'] == 'bool':
                    settings[key] = setting.value.lower() in ('true', '1', 'yes')
                else:
                    settings[key] = setting.value
            else:
                # Use default
                if default['type'] == 'int':
                    settings[key] = int(default['value'])
                elif default['type'] == 'bool':
                    settings[key] = default['value'].lower() in ('true', '1', 'yes')
                else:
                    settings[key] = default['value']

        return settings

    @staticmethod
    def validate_password(password):
        """
        Validate password against policy

        Returns:
            tuple: (is_valid, error_messages)
        """
        policy = PasswordPolicy.get_policy_settings()
        errors = []

        # Check minimum length
        min_length = policy.get('password_min_length', 8)
        if len(password) < min_length:
            errors.append(f"Mật khẩu phải có ít nhất {min_length} ký tự")

        # Check uppercase requirement
        if policy.get('password_require_uppercase', True):
            if not re.search(r'[A-Z]', password):
                errors.append("Mật khẩu phải chứa ít nhất 1 chữ cái viết hoa")

        # Check lowercase requirement
        if policy.get('password_require_lowercase', True):
            if not re.search(r'[a-z]', password):
                errors.append("Mật khẩu phải chứa ít nhất 1 chữ cái viết thường")

        # Check digit requirement
        if policy.get('password_require_digit', True):
            if not re.search(r'\d', password):
                errors.append("Mật khẩu phải chứa ít nhất 1 chữ số")

        # Check special character requirement
        if policy.get('password_require_special', True):
            if not re.search(r'[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\\/~`]', password):
                errors.append("Mật khẩu phải chứa ít nhất 1 ký tự đặc biệt (!@#$%^&*...)")

        return (len(errors) == 0, errors)

    @staticmethod
    def get_policy_description():
        """Get human-readable policy description"""
        policy = PasswordPolicy.get_policy_settings()
        requirements = []

        min_length = policy.get('password_min_length', 8)
        requirements.append(f"Ít nhất {min_length} ký tự")

        if policy.get('password_require_uppercase', True):
            requirements.append("Chữ hoa (A-Z)")

        if policy.get('password_require_lowercase', True):
            requirements.append("Chữ thường (a-z)")

        if policy.get('password_require_digit', True):
            requirements.append("Chữ số (0-9)")

        if policy.get('password_require_special', True):
            requirements.append("Ký tự đặc biệt (!@#$%...)")

        return requirements
