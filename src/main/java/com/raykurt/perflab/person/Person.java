package com.raykurt.perflab.person;

import java.time.LocalDateTime;

public record Person(
        long id,
        String firstName,
        String lastName,
        String email,
        String city,
        LocalDateTime createdAt) {
}
