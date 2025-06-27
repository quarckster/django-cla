from django import forms


class ICLASigningRequestForm(forms.Form):
    email = forms.EmailField(label="Email", required=True)


class CCLASigningRequestForm(forms.Form):
    company = forms.CharField(label="Company Name", required=True)
    authorized_signer_name = forms.CharField(label="Name", required=True)
    authorized_signer_email = forms.EmailField(label="Email", required=True)
