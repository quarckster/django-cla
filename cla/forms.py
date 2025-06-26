from django import forms


class ICLASigningRequestForm(forms.Form):
    email = forms.EmailField(label="Email", required=True)


class CCLASigningRequestForm(forms.Form):
    authorized_signer_name = forms.CharField(label="Authorized signer name", required=True)
    authorized_signer_email = forms.EmailField(label="Authorized signer email", required=True)
    point_of_contact_name = forms.CharField(label="Point of contact name", required=True)
    point_of_contact_email = forms.EmailField(label="Point of contact email", required=True)
