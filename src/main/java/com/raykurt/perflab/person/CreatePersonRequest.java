package com.raykurt.perflab.person;

public record CreatePersonRequest(
        String firstName,
        String lastName,
        String email,
        String city) {

    boolean isValid() {
        return notBlank(firstName) && notBlank(lastName) && notBlank(email) && notBlank(city);
    }

    private static boolean notBlank(String value) {
        return value != null && !value.isBlank();
    }
}
